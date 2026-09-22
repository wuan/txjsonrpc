# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test JSON-RPC over TCP support.
"""

import pytest
from twisted.internet import reactor, defer

from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpclib import VERSION_2
from txjsonrpc_ng.netstring import jsonrpc
from txjsonrpc_ng.netstring.jsonrpc import ( JSONRPC, Proxy, QueryFactory)


class RuntimeErrorTest(RuntimeError):
    pass


class ValueErrorTest(ValueError):
    pass


class ResourceForTest(JSONRPC):
    FAILURE = 666
    NOT_FOUND = jsonrpclib.METHOD_NOT_FOUND

    addSlash = True

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

    jsonrpc_dict.help = 'Help for dict.'


class TestQueryFactory:

    def test_creation(self):
        factory = QueryFactory("mymethod", "myarg1", "myarg2")
        assert factory.protocol.MAX_LENGTH == 99999


@pytest.fixture
def host_port():
    server = reactor.listenTCP(0, jsonrpc.RPCFactory(ResourceForTest),
                               interface="127.0.0.1")
    yield server.getHost().port

    server.stopListening()


@pytest.fixture
def proxy(host_port):
    return Proxy("127.0.0.1", host_port, version=VERSION_2)


class TestJsonRPC:
    timeout = 2

    @pytest.mark.parametrize("method, args, expected", (
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})
    ))
    async def test_results(self, proxy, method, args, expected):
        response = await proxy.callRemote(method, *args)
        assert response == expected

    @pytest.mark.parametrize("code,method_name", (
            (666, "fail"), (666, "deferFail"),
            (12, "fault"),
            (17, "deferFault")
    ))
    async def test_errors(self, proxy, code, method_name):
        with pytest.raises(jsonrpclib.Fault) as exc_info:
            await proxy.callRemote(method_name)

        exc = exc_info.value
        assert isinstance(exc, jsonrpclib.Fault)
        assert exc.faultCode == code


class TestJSONRPCClassMaxLength:

    @pytest.fixture
    def proxy(self, host_port):
        lengths = []

        class Factory(QueryFactory):
            def __init__(self, *args):
                lengths.append(1)
                QueryFactory.__init__(self, *args)

        proxy = Proxy("127.0.0.1", host_port, factoryClass=Factory)
        self.maxLengths = lengths
        return proxy

    async def test_results(self, proxy):
        response = await proxy.callRemote("add", *[2, 3])
        assert response["result"] == 5
        assert self.maxLengths == [1]


class TestJSONRPCMethodMaxLength:

    @pytest.mark.parametrize("method_name, args, expected", (
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})
    ))
    async def test_results(self, proxy, method_name, args, expected):
        lengths = []

        class Factory(QueryFactory):
            def __init__(self, *args):
                lengths.append(1)
                QueryFactory.__init__(self, *args)

        d = await proxy.callRemote(method_name, factoryClass=Factory, *args)
        assert d == expected
        assert len(lengths) == 1
        assert lengths == [1] * 1


class TestJSONRPCIntrospection:

    @pytest.fixture
    def host_port(self):
        server = jsonrpc.RPCFactory(ResourceForTest)
        server.addIntrospection()
        server = reactor.listenTCP(0, server, interface="127.0.0.1")
        yield server.getHost().port
        server.stopListening()

    async def test_list_methods(self, proxy):
        d = await proxy.callRemote("system.listMethods", version=2)

        d.sort()
        assert d == ['add', 'complex', 'defer', 'deferFail',
                     'deferFault', 'dict', 'fail', 'fault',
                     'pair', 'system.listMethods',
                     'system.methodHelp',
                     'system.methodSignature']

        return d

    @pytest.mark.parametrize("method_name, expected", (
            ("defer", "Help for defer."),
            ("fail", ""),
            ("dict", "Help for dict.")
    ))
    async def test_method_help(self, proxy, method_name, expected):
        d = await proxy.callRemote("system.methodHelp", method_name, version=2)
        assert d == expected

    @pytest.mark.parametrize("method_name, expected", (
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])
    ))
    async def test_method_signature(self, proxy, method_name, expected):
        response = await proxy.callRemote("system.methodSignature", method_name, version=2)
        assert response == expected


class TestErrorHandling:
    """
    Errors during dispatch must be reported as JSON-RPC faults, not raised out
    of the protocol handler.
    """

    async def test_unknown_method_returns_fault(self, proxy):
        with pytest.raises(jsonrpclib.Fault) as exc_info:
            await proxy.callRemote("noSuchMethod")
        assert exc_info.value.faultCode == jsonrpclib.METHOD_NOT_FOUND


class TestNamedParameters:
    async def test_named_params(self, proxy):
        response = await proxy.callRemote("add", a=2, b=3)
        assert response == 5
