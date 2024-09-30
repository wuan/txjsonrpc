# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test JSON-RPC over TCP support.
"""
from __future__ import print_function

import pytest
from twisted.internet import reactor, defer
from twisted.trial import unittest

from txjsonrpc import jsonrpclib
from txjsonrpc.meta import version
from txjsonrpc.netstring import jsonrpc
from txjsonrpc.netstring.jsonrpc import (
    JSONRPC, Proxy, QueryFactory)


class TestRuntimeError(RuntimeError):
    pass


class TestValueError(ValueError):
    pass


class Test(JSONRPC):

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
        return defer.fail(TestValueError())

    def jsonrpc_fail(self):
        # Don't add a doc string, it's part of the test.
        raise TestRuntimeError

    def jsonrpc_fault(self):
        return jsonrpclib.Fault(12, "hello")

    def jsonrpc_deferFault(self):
        return defer.fail(jsonrpclib.Fault(17, "hi"))

    def jsonrpc_complex(self):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def jsonrpc_dict(self, map, key):
        return map[key]

    def getFunction(self, functionPath):
        return JSONRPC.getFunction(self, functionPath)

    jsonrpc_dict.help = 'Help for dict.'


class QueryFactoryTestCase(unittest.TestCase):

    def testCreation(self):

        factory = QueryFactory("mymethod", "myarg1", "myarg2")
        self.assertEquals(factory.protocol.MAX_LENGTH, 99999)


class TestJsonRPC:

    timeout = 2

    @pytest.fixture
    def host_port(self):
        server = reactor.listenTCP(0, jsonrpc.RPCFactory(Test),
                                   interface="127.0.0.1")
        yield server.getHost().port

        server.stopListening()

    @pytest.fixture
    def proxy(self, host_port):
        return Proxy("127.0.0.1", host_port)

    async def testResults(self, proxy):

        inputOutput = [
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})]

        for meth, args, outp in inputOutput:
            response = await proxy.callRemote(meth, *args)
            assert response == outp

    def testErrors(self):

        dl = []
        for code, methodName in [(666, "fail"), (666, "deferFail"),
                                 (12, "fault"),
                                 (17, "deferFault")]:
            d = self.proxy().callRemote(methodName)
            d = self.assertFailure(d, jsonrpclib.Fault)
            d.addCallback(
                lambda exc, code=code: self.assertEquals(exc.faultCode, code))
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        d.addCallback(lambda ign: self.flushLoggedErrors())
        return d


class JSONRPCClassMaxLengthTestCase(TestJsonRPC):

    def proxy(self):

        lengths = []

        class Factory(QueryFactory):

            MAX_LENGTH = 1234

            def __init__(self, *args):
                lengths.append(self.MAX_LENGTH)
                QueryFactory.__init__(self, *args)

        proxy = Proxy("127.0.0.1", self.port, factoryClass=Factory)
        self.maxLengths = lengths
        return proxy

    def testResults(self):

        def checkMaxLength(result):
            self.assertEquals(self.maxLengths, [1234])

        d = TestJsonRPC.testResults(self)
        d.addCallback(checkMaxLength)
        return d


class JSONRPCMethodMaxLengthTestCase(TestJsonRPC):

    def testResults(self):

        lengths = []

        inputOutput = [
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})]

        def checkMaxLength(result):
            self.assertEquals(len(lengths), len(inputOutput))
            self.assertEquals(lengths, [1234] * len(inputOutput))

        class Factory(QueryFactory):

            MAX_LENGTH = 1234

            def __init__(self, *args):
                lengths.append(self.MAX_LENGTH)
                QueryFactory.__init__(self, *args)

        def printError(error):
            print("Error!")
            print(error)

        dl = []
        for meth, args, outp in inputOutput:
            d = self.proxy().callRemote(meth, factoryClass=Factory, *args)
            d.addCallback(self.assertEquals, outp)
            d.addErrback(printError)
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        d.addCallback(checkMaxLength)
        return d


class JSONRPCTestIntrospection(TestJsonRPC):

    def setUp(self):
        server = jsonrpc.RPCFactory(Test)
        server.addIntrospection()
        self.p = reactor.listenTCP(0, server, interface="127.0.0.1")
        self.port = self.p.getHost().port

    def testListMethods(self):

        def cbMethods(meths):
            print("methods:", meths)
            meths.sort()
            self.failUnlessEqual(
                meths,
                ['add', 'complex', 'defer', 'deferFail',
                 'deferFault', 'dict', 'fail', 'fault',
                 'pair', 'system.listMethods',
                 'system.methodHelp',
                 'system.methodSignature'])

        d = self.proxy().callRemote("system.listMethods", version=2)
        d.addCallback(cbMethods)
        return d

    def testMethodHelp(self):
        inputOutputs = [
            ("defer", "Help for defer."),
            ("fail", ""),
            ("dict", "Help for dict.")]

        dl = []
        for meth, expected in inputOutputs:
            d = self.proxy().callRemote("system.methodHelp", meth, version=2)
            d.addCallback(self.assertEquals, expected)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def testMethodSignature(self):
        inputOutputs = [
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])]

        dl = []
        for meth, expected in inputOutputs:
            d = self.proxy().callRemote("system.methodSignature", meth)
            d.addCallback(self.assertEquals, expected)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)
