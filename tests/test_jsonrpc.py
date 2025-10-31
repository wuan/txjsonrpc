import pytest
from pytest_twisted import inlineCallbacks

from txjsonrpc_ng.jsonrpc import BaseProxy, BaseQueryFactory
from txjsonrpc_ng.jsonrpclib import Fault, VERSION_PRE1, VERSION_1, VERSION_2


class TestBaseQueryFactory:

    def test_creation(self):
        factory = BaseQueryFactory("someMethod")
        assert factory.payload is not None
        assert factory.deferred is not None

    def test_buildVersionedPayloadPre1(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_PRE1)
        payload = factory._buildVersionedPayload()
        assert payload == '{"method": "", "params": []}'

    def test_buildVersionedPayload1(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_1)
        payload = factory._buildVersionedPayload()
        assert payload == '{"method": "", "params": [], "id": 1}'

    def test_buildVersionedPayload2(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_2)
        payload = factory._buildVersionedPayload()
        assert payload == '{"jsonrpc": "2.0", "method": "", "params": [], "id": 1}'

    @inlineCallbacks
    def test_parseResponseNoJSON(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse("oops")
        
        try:
            yield d
            pytest.fail("Expected an error to be raised")
        except Exception as error:
            assert error.msg == "Expecting value"

    @inlineCallbacks
    def test_parseResponseRandomJSON(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse('{"something": 1}')
        
        result = yield d
        assert result == {"something": 1}

    @inlineCallbacks
    def test_parseResponseFaultData(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse(
            '{"fault": "Fault", "faultCode": 1, "faultString": "oops"}')
        
        try:
            yield d
            pytest.fail("Expected a Fault to be raised")
        except Fault as error:
            assert isinstance(error, Fault)
            assert error.faultCode == 1
            assert error.faultString == "oops"


class TestBaseProxy:

    def test_creation(self):
        proxy = BaseProxy()
        assert proxy.version == VERSION_PRE1
        assert proxy.factoryClass is None

    def test_getVersionDefault(self):
        proxy = BaseProxy()
        version = proxy._getVersion({})
        assert version == VERSION_PRE1

    def test_getVersionPre1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_PRE1})
        assert version == VERSION_PRE1

    def test_getVersion1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_1})
        assert version == VERSION_1

    def test_getFactoryClassDefault(self):
        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({})
        assert factoryClass is None

    def test_getFactoryClassPassed(self):

        class FakeFactory(object):
            pass

        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({"factoryClass": FakeFactory})
        assert factoryClass == FakeFactory
