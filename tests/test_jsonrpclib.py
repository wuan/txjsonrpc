import pytest
from datetime import datetime
from twisted.trial.unittest import TestCase
from twisted.internet import defer
from txjsonrpc_ng import jsonrpclib
from txjsonrpc_ng.jsonrpclib import (
    Fault, VERSION_PRE1, VERSION_1, VERSION_2, dumps, loads,
    JSONRPCEncoder, getparser, Transport, _preV1Request, _v1Request,
    _v1Notification, _v2Request, _v2Notification, SimpleUnmarshaller,
    ServerProxy)


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

    @pytest.mark.parametrize("input,expected", (
            ("1", 1),
            ("\"a\"", "a"),
            ('{"apple": 2}', {"apple": 2}),
            ('[1, 2, "a", "b"]', [1, 2, "a", "b"]),
    ))
    def test_loads(self, input, expected):
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


class TestJSONRPCEncoder:
    """Test JSONRPCEncoder for custom serialization."""

    def test_datetime_serialization(self):
        """Test datetime objects are serialized correctly."""
        encoder = JSONRPCEncoder()
        dt = datetime(2024, 10, 30, 14, 30, 0)
        result = encoder.default(dt)
        assert result == "20241030T14:30:00"

    def test_non_serializable_raises(self):
        """Test that non-serializable objects raise TypeError."""
        encoder = JSONRPCEncoder()
        with pytest.raises(TypeError):
            encoder.default(object())


class TestLoadsErrorHandling:
    """Test error handling in loads."""

    def test_loads_v2_error(self):
        """Test loads with JSON-RPC 2.0 error format."""
        error_json = '{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}'
        with pytest.raises(Fault) as ex_info:
            loads(error_json)
        assert ex_info.value.faultCode == -32600

    def test_loads_v1_error(self):
        """Test loads with JSON-RPC 1.x error format."""
        error_json = '{"error": {"faultCode": -32601, "faultString": "Method not found"}, "id": 1}'
        with pytest.raises(Fault) as ex_info:
            loads(error_json)
        assert ex_info.value.faultCode == -32601


class TestSimpleUnmarshaller:
    """Test SimpleUnmarshaller."""

    def test_close_non_dict(self):
        """Test close returns data as-is when not a dict."""
        parser, marshaller = getparser()
        parser.buffer = '"just a string"'
        parser.close()
        marshaller.parser = parser
        result = marshaller.close()
        assert result == "just a string"


class TestTransport:
    """Test Transport class."""

    def test_getparser(self):
        """Test Transport.getparser returns parser and unmarshaller."""
        transport = Transport()
        parser, marshaller = transport.getparser()
        assert isinstance(parser, jsonrpclib.SimpleParser)
        assert isinstance(marshaller, jsonrpclib.SimpleUnmarshaller)


class TestVersionedRequests:
    """Test version-specific request functions."""

    def test_v1_notification(self):
        """Test _v1Notification creates notification without id."""
        result = _v1Notification("testMethod", [1, 2, 3])
        loaded = loads(result)
        assert loaded["method"] == "testMethod"
        assert loaded["params"] == [1, 2, 3]
        assert loaded["id"] is None

    def test_v2_notification(self):
        """Test _v2Notification creates notification without id."""
        result = _v2Notification("testMethod", [1, 2, 3])
        loaded = loads(result)
        assert loaded["method"] == "testMethod"
        assert loaded["params"] == [1, 2, 3]
        assert loaded["id"] is None


class TestDumps:
    """Additional dumps tests."""

    def test_unknown_version_defaults_to_v1_format(self):
        """Test unknown version falls back to v1 format."""
        obj = {"test": "data"}
        result = dumps(obj, version=999)
        loaded = loads(result)
        assert "result" in loaded
        assert "error" in loaded
        assert "id" in loaded


class TestServerProxy:
    """Test ServerProxy class."""

    def test_init(self):
        """Test ServerProxy initialization."""
        proxy = ServerProxy("http://localhost:8080/", version=VERSION_2)
        assert proxy.version == VERSION_2

    def test_get_versioned_request_pre1(self):
        """Test _getVersionedRequest with VERSION_PRE1."""
        proxy = ServerProxy("http://localhost:8080/", version=VERSION_PRE1)
        request = proxy._getVersionedRequest("testMethod", [1, 2])
        loaded = loads(request)
        assert loaded["method"] == "testMethod"
        assert loaded["params"] == [1, 2]

    def test_get_versioned_request_v1(self):
        """Test _getVersionedRequest with VERSION_1."""
        proxy = ServerProxy("http://localhost:8080/", version=VERSION_1)
        request = proxy._getVersionedRequest("testMethod", [1, 2], 1)
        loaded = loads(request)
        assert loaded["method"] == "testMethod"
        assert loaded["params"] == [1, 2]
        assert loaded["id"] == 1

    def test_get_versioned_request_v2(self):
        """Test _getVersionedRequest with VERSION_2."""
        proxy = ServerProxy("http://localhost:8080/", version=VERSION_2)
        request = proxy._getVersionedRequest("testMethod", [1, 2], 1)
        loaded = loads(request)
        assert loaded["method"] == "testMethod"
        assert loaded["params"] == [1, 2]
        assert loaded["id"] == 1
        assert loaded["jsonrpc"] == "2.0"
