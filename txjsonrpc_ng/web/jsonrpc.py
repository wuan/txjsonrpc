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
import gzip
import io

from .render import renderer_factory

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import xmlrpclib
except ImportError:
    import xmlrpc.client as xmlrpclib

from twisted.web import resource, server
from twisted.internet import defer, reactor
from twisted.python import log, context
from twisted.web.client import Agent, HTTPConnectionPool, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpc import BaseProxy, BaseQueryFactory, BaseSubhandler
from xmlrpc.client import Fault as XMLRPCFault

# Useful so people don't need to import xmlrpclib directly.
Fault = XMLRPCFault
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
    except_map: dict = {}
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
        # JSONP state is per-request; never store it on the shared resource.
        callback = request.args['callback'][0] if 'callback' in request.args else None
        request.jsonp_callback = callback
        if callback:
            request.setHeader("content-type", "text/javascript")
        else:
            request.setHeader("content-type", "application/json")

        id = None
        version = jsonrpclib.VERSION_PRE1
        try:
            parsed = jsonrpclib.loads(content)
            if not isinstance(parsed, dict):
                raise jsonrpclib.Fault(
                    jsonrpclib.INVALID_JSONRPC,
                    "Invalid Request: expected a JSON object")
            functionPath = parsed.get("method")
            if not isinstance(functionPath, str):
                raise jsonrpclib.Fault(
                    jsonrpclib.INVALID_JSONRPC,
                    "Invalid Request: missing method")
            params = parsed.get('params')
            if params is None:
                params = {}
            args, kwargs = [], {}
            if isinstance(params, list):
                args = params
            elif isinstance(params, dict):
                kwargs = params
            else:
                raise jsonrpclib.Fault(
                    jsonrpclib.INVALID_METHOD_PARAMS,
                    "Invalid params: expected an array or object")
            id = parsed.get('id')
            token = None
            if request.requestHeaders.hasHeader(self.auth_token):
                token = request.requestHeaders.getRawHeaders(self.auth_token)[0]
            version_field = parsed.get('jsonrpc')
            if version_field:
                version = int(float(version_field))
            elif id is not None and not version_field:
                version = jsonrpclib.VERSION_1
            else:
                version = jsonrpclib.VERSION_PRE1
            # XXX this all needs to be re-worked to support logic for multiple
            # versions...
            function = self._getFunction(functionPath)
            d = None
            if hasattr(function, 'requires_auth'):
                d = defer.maybeDeferred(self.auth, token, functionPath)
        except jsonrpclib.Fault as f:
            self._cbRender(f, request, id, version)
        except (ValueError, TypeError) as error:
            self._cbRender(
                jsonrpclib.Fault(jsonrpclib.INVALID_JSONRPC, str(error)),
                request, id, version)
        else:
            if hasattr(function, 'with_request'):
                args = [request] + args

            if d is not None:
                d.addCallback(self._call_authenticated, function, args, kwargs)
            else:
                d = defer.maybeDeferred(function, *args, **kwargs)

            def _responseFailed(err, call):
                call.cancel()

            # Register the failure observer *before* wiring up callbacks: a
            # synchronous method can already have fired *d*, and finishing the
            # request discards the observer list.
            request.notifyFinish().addErrback(_responseFailed, d)
            d.addErrback(self._ebRender, id)
            d.addCallback(self._cbRender, request, id, version)
        return server.NOT_DONE_YET

    def _call_authenticated(self, auth_result, function, args, kwargs):
        """
        Enforce the result of L{auth} before invoking the protected method.

        A falsy result (e.g. C{False} or C{None}) denies the request. A truthy
        non-dict result runs the method without extra context; a dict result is
        used as the Twisted context for the call.
        """
        if not auth_result:
            raise Unauthorized("Unauthorized")
        new_context = auth_result if isinstance(auth_result, dict) else {}
        return context.call(new_context, function, *args, **kwargs)

    def _cbRender(self, result, request, id, version):
        if isinstance(result, Handler):
            result = result.result

        if result is not None:
            renderer = renderer_factory(result, id, version, request)

            def string_renderer(result, id, version):
                return self._render_text(result, id, version, request)

            renderer.render(string_renderer)

        request.finish()
        return result

    def _render_text(self, result, id, version, request) -> str:
        callback = getattr(request, 'jsonp_callback', None)
        if version == jsonrpclib.VERSION_PRE1:
            if not isinstance(result, jsonrpclib.Fault):
                result = (result,)
        try:
            s = jsonrpclib.dumps(result, id=id, version=version)
        except Exception:
            f = jsonrpclib.Fault(self.FAILURE, "can't serialize output")
            s = jsonrpclib.dumps(f, id=id, version=version)
        if callback:
            s = "%s(%s)" % (callback, s)
        return str(s)

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

    def __init__(self, agent, url, method, username, password, version=jsonrpclib.VERSION_PRE1, compress=False, *args, **kwargs):
        BaseQueryFactory.__init__(self, method, version, *args, **kwargs)
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

        # Parse URL.  ``urlsplit`` (via ``parsed.hostname``/``parsed.port``)
        # correctly handles IPv6 literals and percent/credential parsing.
        parsed = urlparse.urlsplit(url)
        scheme = parsed.scheme
        path = parsed.path
        host = parsed.hostname
        try:
            port = parsed.port
        except ValueError:
            port = None
        self.username = parsed.username
        self.password = parsed.password
        if username:
            self.username = username
        if password:
            self.password = password
        self.secure = (scheme == 'https')
        self.compress = compress
        self.ssl_ctx_factory = ssl_ctx_factory
        # IPv6 hosts must be bracketed when rebuilding the URL.
        host_for_url = '[%s]' % host if host and ':' in host else host
        if port:
            clean_url = '%s://%s:%d%s' % (scheme, host_for_url, port, path)
        else:
            clean_url = '%s://%s%s' % (scheme, host_for_url, path)
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
        factoryClass = self._getFactoryClass(kwargs)
        # Any remaining keyword arguments are JSON-RPC named parameters.
        params = {key: value for key, value in kwargs.items()
                  if key not in ("version", "factoryClass")}
        factory = factoryClass(self.agent, self.url, method, self.username,
                               self.password, version, self.compress, *args,
                               **params)
        factory._makeRequest()
        return factory.deferred


__all__ = ["JSONRPC", "Handler", "Proxy"]
