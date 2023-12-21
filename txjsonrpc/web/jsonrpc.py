# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
A generic resource for publishing objects via JSON-RPC.

Requires simplejson; can be downloaded from
http://cheeseshop.python.org/pypi/simplejson

API Stability: unstable

Maintainer: U{Duncan McGreggor<mailto:oubiwann@adytum.us>}
"""
from __future__ import nested_scopes, print_function

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import xmlrpclib
except ImportError:
    import xmlrpc.client as xmlrpclib
import gzip
import time
try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

from twisted.web import resource, server
from twisted.internet import defer, reactor
from twisted.python import log, context
from twisted.web import http

from txjsonrpc import jsonrpclib
from txjsonrpc.jsonrpc import BaseProxy, BaseQueryFactory, BaseSubhandler

# Useful so people don't need to import xmlrpclib directly.
Fault = xmlrpclib.Fault
Binary = xmlrpclib.Binary
Boolean = xmlrpclib.Boolean
DateTime = xmlrpclib.DateTime


def with_request(method):
    """
    Decorator to enable the request to be passed as the first argument.
    """
    method.with_request = True
    return method


def requires_auth(method):
    """
    Decorator to enable authentication before resolving the method.
    """
    method.requires_auth = True
    return method


class NoSuchFunction(Fault):
    """
    There is no function by the given name.
    """


class Unauthorized(jsonrpclib.Fault):
    def __init__(self, message):
        Fault.__init__(self, 4000, message)


class Handler:
    """
    Handle a JSON-RPC request and store the state for a request in progress.

    Override the run() method and return result using self.result,
    a Deferred.

    We require this class since we're not using threads, so we can't
    encapsulate state in a running function if we're going  to have
    to wait for results.

    For example, lets say we want to authenticate against twisted.cred,
    run a LDAP query and then pass its result to a database query, all
    as a result of a single JSON-RPC command. We'd use a Handler instance
    to store the state of the running command.
    """

    def __init__(self, resource, *args):
        # the JSON-RPC resource we are connected to
        self.resource = resource
        self.result = defer.Deferred()
        self.run(*args)

    def run(self, *args):
        # event driven equivalent of 'raise UnimplementedError'
        self.result.errback(
            NotImplementedError("Implement run() in subclasses"))


class JSONRPC(resource.Resource, BaseSubhandler):
    """
    A resource that implements JSON-RPC.

    Methods published can return JSON-RPC serializable results, Faults,
    Binary, Boolean, DateTime, Deferreds, or Handler instances.

    By default methods beginning with 'jsonrpc_' are published.
    """

    # Error codes for Twisted, if they conflict with yours then
    # modify them at runtime.
    NOT_FOUND = 8001
    FAILURE = 8002

    isLeaf = 1
    except_map = {}
    auth_token = "Auth-Token"

    def __init__(self):
        resource.Resource.__init__(self)
        BaseSubhandler.__init__(self)

    def render(self, request):
        request.content.seek(0, 0)
        # Unmarshal the JSON-RPC data.
        content = request.content.read()
        if not content and request.method == 'GET' and 'request' in request.args:
            content = request.args['request'][0]
        self.callback = request.args['callback'][0] if 'callback' in request.args else None
        self.is_jsonp = True if self.callback else False
        if not self.is_jsonp:
            request.setHeader("content-type", "application/json")
        else:
            request.setHeader("content-type", "text/javascript")
        parsed = jsonrpclib.loads(content)
        functionPath = parsed.get("method")
        params = parsed.get('params', {})
        args, kwargs = [], {}
        if params.__class__ == list:
            args = params
        else:
            kwargs = params
        id = parsed.get('id')
        token = None
        if request.requestHeaders.hasHeader(self.auth_token):
            token = request.requestHeaders.getRawHeaders(self.auth_token)[0]
        version = parsed.get('jsonrpc')
        if version:
            version = int(float(version))
        elif id and not version:
            version = jsonrpclib.VERSION_1
        else:
            version = jsonrpclib.VERSION_PRE1
        # XXX this all needs to be re-worked to support logic for multiple
        # versions...
        try:
            function = self._getFunction(functionPath)
            d = None
            if hasattr(function, 'requires_auth'):
                d = defer.maybeDeferred(self.auth, token, functionPath)
        except jsonrpclib.Fault as f:
            self._cbRender(f, request, id, version)
        else:
            if hasattr(function, 'with_request'):
                args = [request] + args

            if d:
                d.addCallback(context.call, function, *args, **kwargs)
            else:
                d = defer.maybeDeferred(function, *args, **kwargs)
            d.addErrback(self._ebRender, id)
            d.addCallback(self._cbRender, request, id, version)

            def _responseFailed(err, call):
                call.cancel()

            request.notifyFinish().addErrback(_responseFailed, d)
        return server.NOT_DONE_YET

    def _cbRender(self, original_result, request, id, version):
        result = original_result
        if isinstance(result, Handler):
            result = result.result

        if result is not None:
            s = self._render_text(id, result, version, original_result)
            s = self._handle_compression(s, request, original_result)
            request.setHeader("content-length", str(len(s)))
            request.write(s)

        request.finish()

        return original_result

    def _render_text(self, id, result, version, original_result):
        if isinstance(original_result, dict) and 'result_json' in original_result:
            s = original_result['result_json']
        else:
            try:
                s = jsonrpclib.dumps(result, id=id, version=version) if not self.is_jsonp else "%s(%s)" % (
                    self.callback, jsonrpclib.dumps(result, id=id, version=version))
            except:
                f = jsonrpclib.Fault(self.FAILURE, "can't serialize output")
                s = jsonrpclib.dumps(f, id=id, version=version) if not self.is_jsonp else "%s(%s)" % (
                    self.callback, jsonrpclib.dumps(f, id=id, version=version))
            if isinstance(original_result, dict):
                original_result['result_json'] = s
            else:
                print('original_result:', type(original_result))
        return s

    def _map_exception(self, exception):
        return self.except_map.get(exception, self.FAILURE)

    def _handle_compression(self, data, request, original_result):
        accepted_encoding = request.getHeader('Accept-encoding')

        if accepted_encoding == "gzip" and len(data) >= 1000:
            if original_result and 'result_jsongz' in original_result:
                data = original_result['result_jsongz']
            else:
                original_size = len(data)
                start_time = time.time()

                out_file = StringIO()
                with gzip.GzipFile(mode='wb', fileobj=out_file) as in_file:
                    in_file.write(data.encode())
                data = out_file.getvalue()

                compressed_size = len(data)
                elapsed_time = time.time() - start_time
                break_even = (original_size - compressed_size) / elapsed_time / 1024 / 1024
                print("compress data {} -> {} ({:.1f} %) in {:.2f} ms (break even at {:.1f} MB/s)".format(original_size,
                                                                                                      compressed_size,
                                                                                                      compressed_size * 100 / original_size,
                                                                                                      elapsed_time * 1000,
                                                                                                      break_even))
                if original_result and isinstance(original_result, dict):
                    original_result['result_jsongz'] = data

            request.setHeader("content-encoding", "gzip")
            return data
        else:
            return data.encode()


    def _ebRender(self, failure, id):
        if isinstance(failure.value, jsonrpclib.Fault):
            return failure.value
        log.err(failure)
        message = failure.value.message if hasattr(failure.value, 'message') else repr(failure.value)
        code = self._map_exception(type(failure.value))
        return jsonrpclib.Fault(code, message)

    def auth(self, token, func):
        return True


class QueryProtocol(http.HTTPClient):
    def connectionMade(self):
        self.sendCommand('POST', self.factory.path)
        self.sendHeader('User-Agent', 'Twisted/JSONRPClib')
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('Content-type', 'application/json')
        self.sendHeader('Content-length', str(len(self.factory.payload)))
        if self.factory.user:
            auth = '%s:%s' % (self.factory.user, self.factory.password)
            auth = auth.encode('base64').strip()
            self.sendHeader('Authorization', 'Basic %s' % (auth,))
        self.endHeaders()
        self.transport.write(self.factory.payload)

    def handleStatus(self, version, status, message):
        if status != '200':
            self.factory.badStatus(status, message)

    def handleResponse(self, contents):
        self.factory.parseResponse(contents)


class QueryFactory(BaseQueryFactory):
    deferred = None
    protocol = QueryProtocol

    def __init__(self, path, host, method, user=None, password=None,
                 version=jsonrpclib.VERSION_PRE1, *args):
        BaseQueryFactory.__init__(self, method, version, *args)
        self.path, self.host = path, host
        self.user, self.password = user, password


class Proxy(BaseProxy):
    """
    A Proxy for making remote JSON-RPC calls.

    Pass the URL of the remote JSON-RPC server to the constructor.

    Use proxy.callRemote('foobar', *args) to call remote method
    'foobar' with *args.
    """

    def __init__(self, url, user=None, password=None,
                 version=jsonrpclib.VERSION_PRE1, factoryClass=QueryFactory, ssl_ctx_factory=None):
        """
        @type url: C{str}
        @param url: The URL to which to post method calls.  Calls will be made
        over SSL if the scheme is HTTPS.  If netloc contains username or
        password information, these will be used to authenticate, as long as
        the C{user} and C{password} arguments are not specified.

        @type user: C{str} or None
        @param user: The username with which to authenticate with the server
        when making calls.  If specified, overrides any username information
        embedded in C{url}.  If not specified, a value may be taken from C{url}
        if present.

        @type password: C{str} or None
        @param password: The password with which to authenticate with the
        server when making calls.  If specified, overrides any password
        information embedded in C{url}.  If not specified, a value may be taken
        from C{url} if present.

        @type version: C{int}
        @param version: The version indicates which JSON-RPC spec to support.
        The available choices are jsonrpclib.VERSION*. The default is to use
        the version of the spec that txJSON-RPC was originally released with,
        pre-Version 1.0.

        @type ssl_ctx_factory: C{twisted.internet.ssl.ClientContextFactory} or None
        @param ssl_ctx_factory: SSL client context factory class to use instead
        of default twisted.internet.ssl.ClientContextFactory.
        """
        BaseProxy.__init__(self, version, factoryClass)
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
        netlocParts = netloc.split('@')
        if len(netlocParts) == 2:
            userpass = netlocParts.pop(0).split(':')
            self.user = userpass.pop(0)
            try:
                self.password = userpass.pop(0)
            except:
                self.password = None
        else:
            self.user = self.password = None
        hostport = netlocParts[0].split(':')
        self.host = hostport.pop(0)
        try:
            self.port = int(hostport.pop(0))
        except:
            self.port = None
        self.path = path
        if self.path in ['', None]:
            self.path = '/'
        self.secure = (scheme == 'https')
        if user is not None:
            self.user = user
        if password is not None:
            self.password = password

        self.ssl_ctx_factory = ssl_ctx_factory

    def callRemote(self, method, *args, **kwargs):
        version = self._getVersion(kwargs)
        # XXX generate unique id and pass it as a parameter
        factoryClass = self._getFactoryClass(kwargs)
        factory = factoryClass(self.path, self.host, method, self.user,
                               self.password, version, *args)
        if self.secure:
            from twisted.internet import ssl
            if self.ssl_ctx_factory is None:
                self.ssl_ctx_factory = ssl.ClientContextFactory
            reactor.connectSSL(self.host, self.port or 443,
                               factory, self.ssl_ctx_factory())
        else:
            reactor.connectTCP(self.host, self.port or 80, factory)
        return factory.deferred


__all__ = ["JSONRPC", "Handler", "Proxy"]
