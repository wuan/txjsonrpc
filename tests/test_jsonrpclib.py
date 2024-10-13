import pytest
from twisted.trial.unittest import TestCase
from twisted.internet import defer
from txjsonrpc.jsonrpclib import (
    Fault, VERSION_PRE1, VERSION_1, VERSION_2, dumps, loads)


class TestDump:

    def test_no_version(self):
        object = {"some": "data"}
        result = dumps(object)
        assert result == '{"some": "data"}'

    def test_no_version_error(self):
        object = Fault(123, "message")
        result = dumps(object)
        assert result == ('{"fault": "Fault", "faultCode": 123, '
             '"faultString": "message"}')

    def test_version_pre1(self):
        object = {"some": "data"}
        result = dumps(object, version=VERSION_PRE1)
        assert result == '{"some": "data"}'

    def test_error_version_pre1(self):
        object = Fault(123, "message")
        result = dumps(object, version=VERSION_PRE1)
        assert result == ('{"fault": "Fault", "faultCode": 123, '
             '"faultString": "message"}')

    def test_version_1(self):
        object = {"some": "data"}
        result = dumps(object, version=VERSION_1)
        assert result == '{"result": {"some": "data"}, "error": null, "id": null}'

    def test_error_version_1(self):
        object = Fault(123, "message")
        result = dumps(object, version=VERSION_1)
        assert result == ('{"result": null, "error": {"fault": "Fault", '
             '"faultCode": 123, "faultString": "message"}, "id": null}')

    def test_version_2(self):
        object = {"some": "data"}
        result = dumps(object, version=VERSION_2)
        assert result == '{"jsonrpc": "2.0", "result": {"some": "data"}, "id": null}'

    def test_error_version_2(self):
        object = Fault(123, "message")
        result = dumps(object, version=VERSION_2)
        assert result == ('{"jsonrpc": "2.0", "error": {"message": "message", '
                '"code": 123, "data": ""}, "id": null}')


class TestLoads:

    def test_loads(self):
        jsonInput = ["1", '"a"', '{"apple": 2}', '[1, 2, "a", "b"]']
        expectedResults = [1, "a", {"apple": 2}, [1, 2, "a", "b"]]
        for input, expected in zip(jsonInput, expectedResults):
            unmarshalled = loads(input)
            assert unmarshalled == expected

    @pytest.mark.parametrize("version", [VERSION_PRE1, VERSION_1, VERSION_2])
    def test_loads_fault(self, version):

        object = Fault(123, "message")
        error_string = dumps(object, version=version)

        with pytest.raises(Fault) as ex_info:
            loads(error_string)

        exc = ex_info.value
        assert exc.faultCode == object.faultCode
        assert exc.faultString ==  object.faultString
