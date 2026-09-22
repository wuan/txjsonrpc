# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test JSON-RPC support.
"""
import gzip
import io
import json

import pytest
from mock import MagicMock
from twisted.internet import defer, reactor
from twisted.web import server, static
from twisted.web.http import Request
from twisted.web.test.requesthelper import DummyRequest

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpc import addIntrospection
from txjsonrpc_ng.web import jsonrpc
from txjsonrpc_ng.web.data import CacheableResult
from txjsonrpc_ng.web.jsonrpc import requires_auth, with_request


class RuntimeErrorTest(RuntimeError):
    pass


class ValueErrorTest(ValueError):
    pass


class JsonRpcTest(jsonrpc.JSONRPC):
    FAILURE = 666
    NOT_FOUND = jsonrpclib.METHOD_NOT_FOUND
    SESSION_EXPIRED = 42

    def jsonrpc_add(self, a, b):
        """
        This function add two numbers.
        """
        # The doc string is part of the test.
        return a + b

    jsonrpc_add.signature = [['int', 'int', 'int'],
                             ['double', 'double', 'double']]

    def jsonrpc_pair(self, string, num):
        """
        This function puts the two arguments in an array.
        """
        # The doc string is part of the test.
        return [string, num]

    jsonrpc_pair.signature = [['array', 'string', 'int']]

    def jsonrpc_defer(self, x):
        """
        Help for defer.
        """
        # The doc string is part of the test.
        return defer.succeed(x)

    def jsonrpc_deferFail(self):
        return defer.fail(ValueErrorTest())

    def jsonrpc_fail(self):
        # Don't add a doc string, it's part of the test.
        raise RuntimeErrorTest

    def jsonrpc_fault(self):
        return jsonrpclib.Fault(12, "hello")

    def jsonrpc_deferFault(self):
        return defer.fail(jsonrpclib.Fault(17, "hi"))

    def jsonrpc_complex(self):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def jsonrpc_dict(self, map, key):
        return map[key]

    def jsonrpc_huge(self):
        return "0123456789" * 100 + "X"

    @with_request
    def jsonrpc_with_request(self, request):
        return request is not None and isinstance(request, Request)

    def jsonrpc_none(self):
        return "null"

    def _getFunction(self, functionPath):
        try:
            return jsonrpc.JSONRPC._getFunction(self, functionPath)
        except jsonrpclib.NoSuchFunction:
            if functionPath.startswith("SESSION"):
                raise jsonrpclib.Fault(
                    self.SESSION_EXPIRED, "Session non-existant/expired.")
            else:
                raise

    jsonrpc_dict.help = 'Help for dict.'


class AuthHeaderTest(JsonRpcTest):
    """
    This is used to get the header info so that we can test
    authentication.
    """

    def __init__(self):
        JsonRpcTest.__init__(self)

    @with_request
    def jsonrpc_authinfo(self, request):
        return request.getUser().decode(), request.getPassword().decode()


@pytest.fixture
def site_port():
    p = reactor.listenTCP(0, server.Site(JsonRpcTest()),
                          interface="127.0.0.1")
    yield p.getHost().port
    p.stopListening()


@pytest.fixture
def proxy(site_port):
    return jsonrpc.Proxy("http://127.0.0.1:%d/" % site_port)


@pytest.fixture
def proxy_without_slash(site_port):
    return jsonrpc.Proxy("http://127.0.0.1:%d" % site_port)


class TestJSONRPCTest:

    @pytest.mark.parametrize("method, args, expected", (
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("none", (), "null"),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"}),
            ("with_request", (), True)))
    async def test_results(self, proxy, method, args, expected):
        response = yield proxy.callRemote(method, *args)
        assert response == expected

    @pytest.mark.parametrize("code,method_name", (
            (666, "fail"), (666, "deferFail"),
            (12, "fault"), (-32601, "noSuchMethod"),
            (17, "deferFault")
    ))
    async def test_errors(self, proxy, code, method_name):
        with pytest.raises(jsonrpclib.Fault) as e_info:
            await proxy.callRemote(method_name)
        exc = e_info.value
        assert exc.faultCode == code


class TestJSONRPCIntrospection:

    @pytest.fixture
    def site_port(self):
        json_rpc_test = JsonRpcTest()
        addIntrospection(json_rpc_test)
        p = reactor.listenTCP(0, server.Site(json_rpc_test),
                              interface="127.0.0.1")
        yield p.getHost().port
        p.stopListening()

    async def test_list_methods(self, proxy):
        response = await proxy.callRemote("system.listMethods")
        assert response == ['add', 'complex', 'defer', 'deferFail', 'deferFault', 'dict', 'fail', 'fault', 'huge',
                            'none',
                            'pair', 'system.listMethods', 'system.methodHelp', 'system.methodSignature', 'with_request']

    @pytest.mark.parametrize("method, expected", (
            ("defer", "Help for defer."),
            ("fail", ""),
            ("dict", "Help for dict.")
    ))
    async def test_method_help(self, proxy, method, expected):
        response = await proxy.callRemote("system.methodHelp", method)
        assert response == expected

    @pytest.mark.parametrize("method, expected", (
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])
    ))
    async def test_method_signature(self, proxy, method, expected):
        response = await proxy.callRemote("system.methodSignature", method)
        assert response == expected


class TestCompressedJSONRPC(TestJSONRPCTest):
    """
    Tests that JSON-RPC still works when the client negotiates gzip.
    """

    @pytest.fixture
    def proxy(self, site_port):
        url = "http://127.0.0.1:%d/" % site_port
        return jsonrpc.Proxy(url, compress=True)


class CacheableJsonRpcTest(jsonrpc.JSONRPC):
    compressable_data = "0123456789" * 100 + "X"

    cacheable = CacheableResult("bar")

    compressed_cacheable = CacheableResult(compressable_data)

    def jsonrpc_cacheable(self):
        return self.cacheable

    def jsonrpc_cacheable_compressed(self):
        return self.compressed_cacheable


class TestCacheableJSONRPC:
    """
    Tests for the original, pre-version 1.0 spec that txJSON-RPC was
    originally released as.
    """

    @pytest.fixture
    def site_port(self):
        cacheable_json_rpc_test = CacheableJsonRpcTest()
        p = reactor.listenTCP(0, server.Site(cacheable_json_rpc_test),
                              interface="127.0.0.1")
        yield p.getHost().port
        p.stopListening()

    @pytest.fixture
    def proxy(self, site_port):
        url = "http://127.0.0.1:%d/" % site_port
        return jsonrpc.Proxy(url, compress=True)

    @pytest.mark.parametrize("method, expected", (
            ("cacheable", "bar"),
            ("cacheable_compressed", CacheableJsonRpcTest.compressable_data),
    ))
    async def test_cacheable(self, proxy, method, expected):
        response = await proxy.callRemote(method)
        assert response == expected
        if method == "cacheable":
            assert CacheableJsonRpcTest.cacheable.string_value is not None
        elif method == "cacheable_compressed":
            compressed_data = io.BytesIO(CacheableJsonRpcTest.compressed_cacheable.compressed_value)
            with gzip.GzipFile(mode='rb', fileobj=compressed_data) as in_file:
                contents = in_file.read()
            compressed_data.close()
            assert contents.decode() == CacheableJsonRpcTest.compressed_cacheable.string_value
        response = await proxy.callRemote(method)
        assert response == expected


class TestProxyVersionPre1(TestJSONRPCTest):
    """
    Tests for the original, pre-version 1.0 spec that txJSON-RPC was
    originally released as.
    """

    @pytest.fixture
    def proxy(self, site_port):
        url = "http://127.0.0.1:%d/" % site_port
        return jsonrpc.Proxy(url, version=jsonrpclib.VERSION_PRE1)


class TestProxyVersion1(TestJSONRPCTest):
    """
    Tests for version 1.0.
    """

    @pytest.fixture
    def proxy(self, site_port):
        url = "http://127.0.0.1:%d/" % site_port
        return jsonrpc.Proxy(url, version=jsonrpclib.VERSION_1)


class TestProxyVersion2(TestJSONRPCTest):
    """
    Tests for the version 2.0.
    """

    @pytest.fixture
    def proxy(self, site_port):
        url = "http://127.0.0.1:%d/" % site_port
        return jsonrpc.Proxy(url, version=jsonrpclib.VERSION_2)


class TestCompression:

    async def test_compressed_payload(self, site_port):
        proxy = jsonrpc.Proxy("http://127.0.0.1:%d/" % (site_port), compress=True)
        response = await proxy.callRemote("huge")
        assert len(response) > 1000


class TestAuthenticatedProxy(TestJSONRPCTest):
    """
    Test with authenticated proxy. We run this with the same inout/ouput as
    above.
    """
    user = "username"
    password = "asecret"

    @pytest.fixture
    def site_port(self):
        p = reactor.listenTCP(0, server.Site(AuthHeaderTest()),
                              interface="127.0.0.1")
        yield p.getHost().port
        p.stopListening()

    @pytest.fixture
    def proxy(self, site_port):
        return jsonrpc.Proxy("http://%s:%s@127.0.0.1:%d/" % (self.user, self.password, site_port))

    async def test_auth_info_in_url(self, site_port):
        proxy = jsonrpc.Proxy("http://%s:%s@127.0.0.1:%d/" % (self.user, self.password, site_port))
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]

    async def test_explicit_auth_info(self, site_port):
        proxy = jsonrpc.Proxy("http://127.0.0.1:%d/" % (site_port), self.user, self.password)
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]

    async def test_explicit_auth_info_override(self, site_port):
        proxy = jsonrpc.Proxy("http://wrong:info@127.0.0.1:%d/" % (site_port), self.user, self.password)
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]


class TestProxyErrorHandling:

    @pytest.fixture
    def site_port(self):
        resource = static.File(__file__)
        resource.isLeaf = True
        p = reactor.listenTCP(0, server.Site(resource),
                              interface="127.0.0.1")
        yield p.getHost().port
        p.stopListening()

    async def test_erroneous_response(self, site_port):
        proxy = jsonrpc.Proxy(
            "http://127.0.0.1:%d/" % (site_port,))
        with pytest.raises(Exception):
            await proxy.callRemote("someMethod")


class TestRenderer:
    """Test render.py classes."""

    def test_default_renderer_basic(self):
        """Test DefaultRenderer basic rendering."""
        from txjsonrpc_ng.web.render import DefaultRenderer

        # Create mock request
        request = MagicMock()
        request.getHeader.return_value = None
        request.setHeader = MagicMock()
        request.write = MagicMock()

        renderer = DefaultRenderer("test_result", "id1", 1, request)
        assert renderer.id == "id1"
        assert renderer.version == 1

        # Mock string_renderer
        def string_renderer(result, id, version):
            return f"result:{result},id:{id},v:{version}"

        renderer.render(string_renderer)
        request.write.assert_called_once()

    def test_cacheable_result_renderer_with_cached_value(self):
        """Test CacheableResultRenderer with cached compressed value."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer

        # Create mock request
        request = MagicMock()
        request.getHeader.return_value = None
        request.setHeader = MagicMock()
        request.write = MagicMock()

        # Create CacheableResult with cached values
        cache_result = CacheableResult("test_value")
        cache_result.string_value = "cached_string"
        cache_result.compressed_value = b"cached_compressed"
        cache_result.render_key = (1, "id1")

        renderer = CacheableResultRenderer(cache_result, "id1", 1, request)

        def string_renderer(result, id, version):
            return f"result:{result}"

        renderer.render(string_renderer)
        request.write.assert_called_once()

    def test_cacheable_result_renderer_without_cached_value(self):
        """Test CacheableResultRenderer without cached values."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer

        # Create mock request
        request = MagicMock()
        request.getHeader.return_value = None
        request.setHeader = MagicMock()
        request.write = MagicMock()

        # Create CacheableResult without cached values
        cache_result = CacheableResult("test_value")
        assert cache_result.string_value is None
        assert cache_result.compressed_value is None

        renderer = CacheableResultRenderer(cache_result, "id1", 1, request)

        def string_renderer(result, id, version):
            return "rendered_result_string"

        renderer.render(string_renderer)

        # Should have called string_renderer and stored result
        assert cache_result.string_value == "rendered_result_string"
        request.write.assert_called_once()

    def test_renderer_factory_cacheable(self):
        """Test renderer_factory returns CacheableResultRenderer for CacheableResult."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer, renderer_factory

        request = MagicMock()
        request.getHeader.return_value = None

        cache_result = CacheableResult("test")
        renderer = renderer_factory(cache_result, "id1", 1, request)
        assert isinstance(renderer, CacheableResultRenderer)

    def test_renderer_factory_default(self):
        """Test renderer_factory returns DefaultRenderer for regular result."""
        from txjsonrpc_ng.web.render import DefaultRenderer, renderer_factory

        request = MagicMock()
        request.getHeader.return_value = None

        renderer = renderer_factory("regular_result", "id1", 1, request)
        assert isinstance(renderer, DefaultRenderer)

    def test_cacheable_result_renderer_rerenders_for_other_version_or_id(self):
        """A cached rendering must not leak into a different (version, id)."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer

        request = MagicMock()
        request.getHeader.return_value = None
        request.setHeader = MagicMock()
        request.write = MagicMock()

        cache_result = CacheableResult("test_value")

        def string_renderer(result, id, version):
            return f"result:{result},id:{id},v:{version}"

        CacheableResultRenderer(cache_result, 0, 0, request).render(string_renderer)
        assert cache_result.string_value == "result:test_value,id:0,v:0"

        request.write.reset_mock()
        CacheableResultRenderer(cache_result, 7, 1, request).render(string_renderer)
        assert cache_result.string_value == "result:test_value,id:7,v:1"
        request.write.assert_called_once_with(b"result:test_value,id:7,v:1")

    def test_cacheable_result_renderer_reuses_matching_version_and_id(self):
        """A cached rendering is reused for the same (version, id)."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer

        request = MagicMock()
        request.getHeader.return_value = None
        request.setHeader = MagicMock()
        request.write = MagicMock()

        cache_result = CacheableResult("test_value")
        calls = []

        def string_renderer(result, id, version):
            calls.append((id, version))
            return f"result:{result},id:{id},v:{version}"

        CacheableResultRenderer(cache_result, 7, 1, request).render(string_renderer)
        CacheableResultRenderer(cache_result, 7, 1, request).render(string_renderer)
        assert calls == [(7, 1)]

    def test_cacheable_result_renderer_discards_stale_compression(self):
        """Re-rendering for another version/id must drop the stale gzip body."""
        from txjsonrpc_ng.web.render import CacheableResultRenderer

        request = MagicMock()
        request.getHeader.return_value = "gzip"
        request.setHeader = MagicMock()
        request.write = MagicMock()

        cache_result = CacheableResult("x" * 2000)

        def string_renderer(result, id, version):
            return f"{result}-{id}-{version}"

        CacheableResultRenderer(cache_result, 1, 1, request).render(string_renderer)
        first_compressed = cache_result.compressed_value
        assert first_compressed is not None

        CacheableResultRenderer(cache_result, 2, 1, request).render(string_renderer)
        # The compressed body belongs to the previous rendering and must be
        # replaced by one produced from the current string.
        assert cache_result.compressed_value != first_compressed
        with gzip.GzipFile(fileobj=io.BytesIO(cache_result.compressed_value)) as in_file:
            assert in_file.read().decode() == "x" * 2000 + "-2-1"


def _make_request(body, **args):
    """
    Build a DummyRequest carrying *body* as the POST content.
    """
    request = DummyRequest([b''])
    request.content = io.BytesIO(body)
    request.method = b'POST'
    for key, value in args.items():
        request.args[key] = [value]
    request._finishedDeferreds = []
    return request


def _render(resource, body, **args):
    request = _make_request(body, **args)
    resource.render(request)
    return request, b"".join(request.written)


class TestInvalidRequests:
    """
    Malformed or schema-invalid requests must yield a JSON-RPC fault rather
    than an unhandled exception (HTTP 500).
    """

    class Resource(jsonrpc.JSONRPC):
        def jsonrpc_complex(self):
            return {"a": ["b", "c", 12, []], "D": "foo"}

    @pytest.mark.parametrize("body", (
            b"{not json",
            b"",
            b'[{"jsonrpc": "2.0", "method": "complex", "params": [], "id": 1}]',
            b'{"jsonrpc": "2.0", "id": 1}',
    ))
    def test_invalid_request_returns_fault(self, body):
        _, written = _render(self.Resource(), body)
        with pytest.raises(jsonrpclib.Fault):
            jsonrpclib.loads(written.decode())

    def test_params_null_is_treated_as_no_params(self):
        body = json.dumps({
            "jsonrpc": "2.0", "method": "complex", "params": None, "id": 1,
        }).encode()
        _, written = _render(self.Resource(), body)
        parsed = json.loads(written)
        assert parsed["result"] == {"a": ["b", "c", 12, []], "D": "foo"}

    def test_id_zero_selects_version_1_envelope(self):
        body = json.dumps({"method": "complex", "params": [], "id": 0}).encode()
        _, written = _render(self.Resource(), body)
        parsed = json.loads(written)
        # A pre-1.0 response would be the bare result value; an id of 0 must
        # still be recognised as JSON-RPC 1.0 and wrapped in a result envelope.
        assert parsed["id"] == 0
        assert parsed["result"] == {"a": ["b", "c", 12, []], "D": "foo"}


class TestLegacyZeroIdCompatibility:
    """
    Non-conforming pre-1.0 clients may use a fixed ``id`` of ``0`` yet expect
    the bare-array pre-1.0 envelope.  Because such a request is
    indistinguishable from JSON-RPC 1.0, the legacy behaviour must be opted
    into explicitly via ``treat_zero_id_as_pre1``.
    """

    class LegacyResource(jsonrpc.JSONRPC):
        treat_zero_id_as_pre1 = True

        def jsonrpc_complex(self):
            return {"a": ["b", "c", 12, []], "D": "foo"}

    def test_zero_id_selects_pre1_envelope_when_enabled(self):
        body = json.dumps({"method": "complex", "params": [], "id": 0}).encode()
        _, written = _render(self.LegacyResource(), body)
        parsed = json.loads(written)
        # The pre-1.0 envelope is a bare, single-element array.
        assert isinstance(parsed, list)
        assert parsed == [{"a": ["b", "c", 12, []], "D": "foo"}]

    def test_non_zero_id_still_selects_version_1_when_enabled(self):
        body = json.dumps({"method": "complex", "params": [], "id": 1}).encode()
        _, written = _render(self.LegacyResource(), body)
        parsed = json.loads(written)
        assert parsed["id"] == 1
        assert parsed["result"] == {"a": ["b", "c", 12, []], "D": "foo"}

    def test_missing_id_still_selects_pre1_when_enabled(self):
        body = json.dumps({"method": "complex", "params": []}).encode()
        _, written = _render(self.LegacyResource(), body)
        assert json.loads(written) == [{"a": ["b", "c", 12, []], "D": "foo"}]

    def test_explicit_version_2_wins_over_legacy_flag(self):
        body = json.dumps({
            "jsonrpc": "2.0", "method": "complex", "params": [], "id": 0,
        }).encode()
        _, written = _render(self.LegacyResource(), body)
        parsed = json.loads(written)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["result"] == {"a": ["b", "c", 12, []], "D": "foo"}


class CacheableMixedVersionResource(jsonrpc.JSONRPC):
    """A resource whose cached result is shared across protocol dialects."""

    treat_zero_id_as_pre1 = True

    def __init__(self):
        super().__init__()
        self.result = CacheableResult({"a": 1})

    def jsonrpc_cached(self):
        return self.result


class TestCacheableResultEnvelopeIsolation:
    """A cached serialization must not leak between protocol dialects.

    A legacy ``id=0`` request caches a bare pre-1.0 array on the
    :class:`CacheableResult`.  A following v1 request must still receive a
    version-appropriate object with its own id, not the stale legacy array.
    """

    def test_legacy_then_versioned_request(self):
        resource = CacheableMixedVersionResource()

        _, legacy = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 0,
        }).encode())
        assert json.loads(legacy) == [{"a": 1}]

        _, versioned = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 5,
        }).encode())
        parsed = json.loads(versioned)
        assert parsed["id"] == 5
        assert parsed["result"] == {"a": 1}

    def test_versioned_then_legacy_request(self):
        resource = CacheableMixedVersionResource()

        _, versioned = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 5,
        }).encode())
        assert json.loads(versioned)["id"] == 5

        _, legacy = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 0,
        }).encode())
        assert json.loads(legacy) == [{"a": 1}]

    def test_legacy_v1_v2_sequence(self):
        """The exact sequence the live legacy-protocol suite exercises."""
        resource = CacheableMixedVersionResource()

        _, legacy = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 0,
        }).encode())
        assert json.loads(legacy) == [{"a": 1}]

        _, v1 = _render(resource, json.dumps({
            "method": "cached", "params": [], "id": 1,
        }).encode())
        v1_parsed = json.loads(v1)
        assert v1_parsed["id"] == 1
        assert v1_parsed["result"] == {"a": 1}

        _, v2 = _render(resource, json.dumps({
            "jsonrpc": "2.0", "method": "cached", "params": [], "id": 0,
        }).encode())
        v2_parsed = json.loads(v2)
        assert v2_parsed["jsonrpc"] == "2.0"
        assert v2_parsed["result"] == {"a": 1}


class AuthEnforcedJSONRPC(jsonrpc.JSONRPC):
    executed = False

    def auth(self, token, func):
        return False

    @requires_auth
    def jsonrpc_secret(self):
        AuthEnforcedJSONRPC.executed = True
        return "secret"


class TestAuthEnforcement:
    """
    A falsy result from ``auth`` must deny the request, not merely delay it.
    """

    def test_denied_auth_does_not_execute(self):
        AuthEnforcedJSONRPC.executed = False
        body = jsonrpclib._v1Request("secret", [], 1).encode()
        _, written = _render(AuthEnforcedJSONRPC(), body)
        with pytest.raises(jsonrpclib.Fault) as exc_info:
            jsonrpclib.loads(written.decode())
        assert exc_info.value.faultCode == 4000
        assert AuthEnforcedJSONRPC.executed is False


class JsonpJsonRpcTest(jsonrpc.JSONRPC):
    def __init__(self):
        super().__init__()
        self.pending = {}

    def jsonrpc_slow(self, n):
        d = defer.Deferred()
        self.pending[n] = d
        return d


class TestJsonpIsolation:
    """
    Interleaved JSONP requests must not leak their callback names into each
    other's responses.
    """

    def test_interleaved_requests_keep_callbacks(self):
        resource = JsonpJsonRpcTest()
        request_a = _make_request(
            jsonrpclib._v1Request("slow", ["a"], 1).encode(),
            callback="CALLBACK_A")
        request_b = _make_request(
            jsonrpclib._v1Request("slow", ["b"], 2).encode(),
            callback="CALLBACK_B")

        resource.render(request_a)
        resource.render(request_b)
        resource.pending["a"].callback("result-A")

        body_a = b"".join(request_a.written).decode()
        body_b = b"".join(request_b.written).decode()
        assert body_a.startswith("CALLBACK_A(")
        assert "result-A" in body_a
        assert body_b == ""


class TestNamedParameters:
    """
    Client keyword arguments are forwarded as JSON-RPC named parameters.
    """

    async def test_named_params(self, proxy):
        response = await proxy.callRemote("add", a=2, b=3)
        assert response == 5
