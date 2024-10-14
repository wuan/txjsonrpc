# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test JSON-RPC support.
"""
import gzip
import io

import pytest
from twisted.internet import reactor, defer
from twisted.web import server, static
from twisted.web.http import Request

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpc import addIntrospection
from txjsonrpc_ng.web import jsonrpc
from txjsonrpc_ng.web.data import CacheableResult
from txjsonrpc_ng.web.jsonrpc import with_request


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
    async def testMethodHelp(self, proxy, method, expected):
        response = await proxy.callRemote("system.methodHelp", method)
        assert response == expected

    @pytest.mark.parametrize("method, expected", (
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])
    ))
    async def testMethodSignature(self, proxy, method, expected):
        response = await proxy.callRemote("system.methodSignature", method)
        assert response == expected


class TestCompressedJSONRPC(TestJSONRPCTest):
    """
    Tests for the original, pre-version 1.0 spec that txJSON-RPC was
    originally released as.
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

    async def test_auth_info_in_URL(self, site_port):
        proxy = jsonrpc.Proxy("http://%s:%s@127.0.0.1:%d/" % (self.user, self.password, site_port))
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]

    async def testExplicitAuthInfo(self, site_port):
        proxy = jsonrpc.Proxy("http://127.0.0.1:%d/" % (site_port), self.user, self.password)
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]

    async def testExplicitAuthInfoOverride(self, site_port):
        proxy = jsonrpc.Proxy("http://wrong:info@127.0.0.1:%d/" % (site_port), self.user, self.password)
        response = await proxy.callRemote("authinfo")
        assert response == [self.user, self.password]


class ProxyErrorHandlingTestCase:

    @pytest.fixture
    def site_port(self):
        resource = static.File(__file__)
        resource.isLeaf = True
        p = reactor.listenTCP(0, server.Site(resource),
                              interface="127.0.0.1")
        yield p.getHost().port
        p.stopListening()

    async def testErroneousResponse(self, site_port):
        proxy = jsonrpc.Proxy(
            "http://127.0.0.1:%d/" % (site_port,))
        return self.assertFailure(
            await proxy.callRemote("someMethod"), Exception)
