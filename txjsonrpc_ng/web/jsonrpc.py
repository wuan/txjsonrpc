# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
A generic resource for publishing objects via JSON-RPC.

Requires simplejson; can be downloaded from
http://cheeseshop.python.org/pypi/simplejson

API Stability: unstable

Maintainer: U{Duncan McGreggor<mailto:oubiwann@adytum.us>}
"""

import codecs
import io

from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from .render import renderer_factory

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import xmlrpclib
except ImportError:
    import xmlrpc.client as xmlrpclib
import gzip

from twisted.web import resource, server
from twisted.internet import defer, reactor
from twisted.python import log, context
from twisted.web import http
from twisted.web.client import Agent, HTTPConnectionPool, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpc import BaseProxy, BaseQueryFactory, BaseSubhandler

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
        content = request.content.read().decode()
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

    def _cbRender(self, result, request, id, version):
        if isinstance(result, Handler):
            result = result.result

        if result is not None:
            renderer = renderer_factory(result, id, version, request)
            renderer.render(self._render_text)

        request.finish()
        return result

    def _render_text(self, result, id, version) -> str:
        if version == jsonrpclib.VERSION_PRE1:
            if not isinstance(result, jsonrpclib.Fault):
                result = (result,)
        try:
            s = jsonrpclib.dumps(result, id=id, version=version) if not self.is_jsonp else "%s(%s)" % (
                self.callback, jsonrpclib.dumps(result, id=id, version=version))
        except:
            f = jsonrpclib.Fault(self.FAILURE, "can't serialize output")
            s = jsonrpclib.dumps(f, id=id, version=version) if not self.is_jsonp else "%s(%s)" % (
                self.callback, jsonrpclib.dumps(f, id=id, version=version))
        return s

    def _map_exception(self, exception):
        return self.except_map.get(exception, self.FAILURE)

    def _ebRender(self, failure, id):
        if isinstance(failure.value, jsonrpclib.Fault):
            return failure.value
        log.err(failure)
        message = failure.value.message if hasattr(failure.value, 'message') else repr(failure.value)
        code = self._map_exception(type(failure.value))
        return jsonrpclib.Fault(code, message)

    def auth(self, token, func):
        return True


@implementer(IBodyProducer)
class StringProducer:
    """
    A simple body producer for sending string data with Agent.
    """
    def __init__(self, body):
        self.body = body.encode('utf-8') if isinstance(body, str) else body
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class QueryFactory(BaseQueryFactory):
    """
    Factory for making JSON-RPC requests using twisted.web.client.Agent.
    """
    deferred = None

    def __init__(self, agent, url, method, username, password, version=jsonrpclib.VERSION_PRE1, compress=False, *args):
        BaseQueryFactory.__init__(self, method, version, *args)
        self.agent = agent
        self.url = url
        self.username = username
        self.password = password
        self.compress = compress

    def _makeRequest(self):
        """
        Make the HTTP request using Agent.
        """
        # Build headers
        headers_dict = {
            b'User-Agent': [b'Twisted/JSONRPClib'],
            # b'Host': [self.host.encode('utf-8')],
            b'Content-Type': [b'application/json'],
        }

        if self.compress:
            headers_dict[b'Accept-Encoding'] = [b'gzip']

        if self.username:
            auth = '%s:%s' % (self.username, self.password)
            auth = codecs.encode(auth.encode(), 'base64').strip()
            headers_dict[b'Authorization'] = [b'Basic ' + auth]

        headers = Headers(headers_dict)

        # Create body producer
        body_producer = StringProducer(self.payload)

        # Make request
        d = self.agent.request(
            b'POST',
            self.url.encode('utf-8'),
            headers,
            body_producer
        )

        # Add callbacks
        d.addCallback(self._handleResponse)
        d.addErrback(self._handleError)
        return d

    def _handleResponse(self, response):
        """
        Handle the HTTP response.
        """
        if response.code != 200:
            self.badStatus(str(response.code), response.phrase.decode('utf-8'))
            return response

        # Read the response body
        d = readBody(response)
        d.addCallback(self._processBody, response)
        d.addErrback(self._handleError)
        return d

    def _processBody(self, body, response):
        """
        Process the response body, handling gzip compression if needed.
        """
        # Check for gzip compression
        content_encoding = response.headers.getRawHeaders(b'content-encoding')
        if content_encoding and b'gzip' in [enc.lower() for enc in content_encoding]:
            compressed_file = io.BytesIO(body)
            with gzip.GzipFile(mode='rb', fileobj=compressed_file) as in_file:
                body = in_file.read()
            compressed_file.close()

        # Parse the response
        self.parseResponse(body.decode('utf-8'))

    def _handleError(self, failure):
        """
        Handle errors during the request.
        """
        if self.deferred is not None:
            self.deferred.errback(failure)
            self.deferred = None


class Proxy(BaseProxy):
    """
    A Proxy for making remote JSON-RPC calls.

    Pass the URL of the remote JSON-RPC server to the constructor.

    Use proxy.callRemote('foobar', *args) to call remote method
    'foobar' with *args.
    """

    def __init__(self, url, username=None, password=None,
                 version=jsonrpclib.VERSION_PRE1, compress=False, factoryClass=QueryFactory,
                 ssl_ctx_factory=None, pool=None):
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

        @type pool: C{twisted.web.client.HTTPConnectionPool} or None
        @param pool: Connection pool to use for the Agent. If None, a new pool
        will be created.
        """
        BaseProxy.__init__(self, version, factoryClass)

        # Parse URL
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
        netlocParts = netloc.split('@')
        if len(netlocParts) == 2:
            userpass = netlocParts.pop(0).split(':')
            self.username = userpass.pop(0)
            try:
                self.password = userpass.pop(0)
            except:
                self.password = None
        else:
            self.username = self.password = None
        if username:
            self.username = username
        if password:
            self.password = password
        hostport = netlocParts[0].split(':')
        host = hostport.pop(0)
        try:
            port = int(hostport.pop(0))
        except:
            port = None
        self.secure = (scheme == 'https')
        self.compress = compress
        self.ssl_ctx_factory = ssl_ctx_factory
        if port:
            clean_url = '%s://%s:%d%s' % (scheme, host, port, path)
        else:
            clean_url = '%s://%s%s' % (scheme, host, path)
        self.url = clean_url

        # Create Agent
        if pool is None:
            pool = HTTPConnectionPool(reactor)

        if self.secure:
            from twisted.internet import ssl
            if self.ssl_ctx_factory is None:
                self.ssl_ctx_factory = ssl.ClientContextFactory
            # For HTTPS, we need to pass the context factory
            self.agent = Agent(reactor, self.ssl_ctx_factory(), pool=pool)
        else:
            self.agent = Agent(reactor, pool=pool)

    def callRemote(self, method, *args, **kwargs):
        version = self._getVersion(kwargs)
        # XXX generate unique id and pass it as a parameter
        factoryClass = self._getFactoryClass(kwargs)
        factory = factoryClass(self.agent, self.url, method, self.username, self.password, version, self.compress, *args)
        factory._makeRequest()
        return factory.deferred


__all__ = ["JSONRPC", "Handler", "Proxy"]
