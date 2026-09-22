import json

import pytest

from txjsonrpc_ng.jsonrpc import BaseProxy, BaseQueryFactory
from txjsonrpc_ng.jsonrpclib import Fault, VERSION_PRE1, VERSION_1, VERSION_2


class TestBaseQueryFactory:

    def test_creation(self):
        factory = BaseQueryFactory("someMethod")
        assert factory.payload is not None
        assert factory.deferred is not None

    def test_build_versioned_payload_pre1(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_PRE1)
        payload = factory._buildVersionedPayload()
        assert payload == '{"method": "", "params": []}'

    def test_build_versioned_payload_1(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_1)
        payload = factory._buildVersionedPayload()
        assert payload == '{"method": "", "params": [], "id": %d}' % factory.id

    def test_build_versioned_payload_2(self):
        factory = BaseQueryFactory("someMethod", version=VERSION_2)
        payload = factory._buildVersionedPayload()
        assert payload == '{"jsonrpc": "2.0", "method": "", "params": [], "id": %d}' % factory.id

    async def test_parse_response_no_json(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse("oops")

        with pytest.raises(Exception) as exc_info:
            await d
        assert exc_info.value.msg == "Expecting value"

    async def test_parse_response_random_json(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse('{"something": 1}')

        result = await d
        assert result == {"something": 1}

    async def test_parse_response_fault_data(self):
        factory = BaseQueryFactory("someMethod")
        d = factory.deferred
        factory.parseResponse(
            '{"fault": "Fault", "faultCode": 1, "faultString": "oops"}')

        with pytest.raises(Fault) as exc_info:
            await d
        assert exc_info.value.faultCode == 1
        assert exc_info.value.faultString == "oops"


class TestBaseProxy:

    def test_creation(self):
        proxy = BaseProxy()
        assert proxy.version == VERSION_PRE1
        assert proxy.factoryClass is None

    def test_get_version_default(self):
        proxy = BaseProxy()
        version = proxy._getVersion({})
        assert version == VERSION_PRE1

    def test_get_version_pre1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_PRE1})
        assert version == VERSION_PRE1

    def test_get_version_1(self):
        proxy = BaseProxy()
        version = proxy._getVersion({"version": VERSION_1})
        assert version == VERSION_1

    def test_get_factory_class_default(self):
        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({})
        assert factoryClass is None

    def test_get_factory_class_passed(self):

        class FakeFactory(object):
            pass

        proxy = BaseProxy()
        factoryClass = proxy._getFactoryClass({"factoryClass": FakeFactory})
        assert factoryClass == FakeFactory


class TestUniqueIds:

    def test_ids_are_unique(self):
        factories = [BaseQueryFactory("someMethod", version=VERSION_1)
                     for _ in range(5)]
        ids = [factory.id for factory in factories]
        assert len(set(ids)) == len(ids)

    def test_named_params_payload(self):
        factory = BaseQueryFactory(
            "someMethod", version=VERSION_2, alpha=1, beta=2)
        payload = json.loads(factory.payload)
        assert payload["params"] == {"alpha": 1, "beta": 2}
