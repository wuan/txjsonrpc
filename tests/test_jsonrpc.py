from twisted.trial.unittest import TestCase

from txjsonrpc_ng.jsonrpc import BaseProxy, BaseQueryFactory
from txjsonrpc_ng.jsonrpclib import Fault, VERSION_PRE1, VERSION_1, VERSION_2


class BaseQueryFactoryTestCase(TestCase):

    def test_creation(self):
        factory = BaseQueryFactory("someMethod")
        self.assertTrue(factory.payload is not None)
        self.assertTrue(factory.deferred is not None)

    def test_buildVersionedPayloadPre1(self):
        factory = BaseQueryFactory("someMethod",version=VERSION_PRE1)
        payload = factory._buildVersionedPayload()
        self.assertEquals(
            payload, '{"method": "", "params": []}')

    def test_buildVersionedPayload1(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_1)
        payload = factory._buildVersionedPayload()
        self.assertEquals(
            payload,
            '{"method": "", "params": [], "id": 1}')

    def test_buildVersionedPayload2(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_2)
        payload = factory._buildVersionedPayload()
        self.assertEquals(
            payload,
            '{"jsonrpc": "2.0", "method": "", "params": [], "id": 1}')

    def test_parseResponseNoJSON(self):

        def check_error(error):
            self.assertEquals(
                error.value.msg, "Expecting value")

        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse("oops")
        return d.addErrback(check_error)

    def test_parseResponseRandomJSON(self):

        def check_result(result):
            self.assertEquals(
                result, {u'something': 1})

        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse('{"something": 1}')
        return d.addCallback(check_result)

    def test_parseResponseFaultData(self):

        def check_error(error):
            self.assertTrue(isinstance(error.value, Fault))
            self.assertEquals(error.value.faultCode, 1)
            self.assertEquals(error.value.faultString, u"oops")

        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse(
            '{"fault": "Fault", "faultCode": 1, "faultString": "oops"}')
        return d.addErrback(check_error)


class BaseProxyTestCase(TestCase):

    def test_creation(self):
        proxy = BaseProxy()
        self.assertEquals(proxy.version, VERSION_PRE1)
        self.assertEquals(proxy.factoryClass, None)

    def test_getVersionDefault(self):
        proxy = BaseProxy()
        version = proxy._getVersion({})
        self.assertEquals(version, VERSION_PRE1)

    def test_getVersionPre1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_PRE1})
        self.assertEquals(version, VERSION_PRE1)

    def test_getVersion1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_1})
        self.assertEquals(version, VERSION_1)

    def test_getFactoryClassDefault(self):
        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({})
        self.assertEquals(factoryClass, None)

    def test_getFactoryClassPassed(self):

        class FakeFactory(object):
            pass

        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({"factoryClass": FakeFactory})
        self.assertEquals(factoryClass, FakeFactory)
