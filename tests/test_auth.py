import pytest
from zope.interface import Interface

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse

from txjsonrpc_ng.auth import HTTPAuthRealm, wrapResource


class TestHTTPAuthRealm:

    def setup_method(self):
        self.realm = HTTPAuthRealm("a resource")

    def test_creation(self):
        assert self.realm.resource == "a resource"

    def test_request_avatar_web(self):
        from twisted.web.resource import IResource
        interface, resource, logoutMethod = self.realm.requestAvatar(
            "an id", None, IResource)
        assert interface == IResource
        assert resource == self.realm.resource
        assert logoutMethod == self.realm.logout

    def test_request_avatar_non_web(self):
        with pytest.raises(NotImplementedError):
            self.realm.requestAvatar("an id", None, [Interface])


class TestWrapResource:

    def setup_method(self):
        self.checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser("joe", "blow")

    def test_wrap_resource_web(self):
        from twisted.web.resource import IResource, Resource
        root = Resource()
        wrapped = wrapResource(root, [self.checker])
        assert IResource.providedBy(wrapped)


class TestWrapResourceDefaults:
    """
    ``wrapResource`` must not mutate its arguments nor share the default
    credential-factory list between calls.
    """

    def setup_method(self):
        self.checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser("joe", "blow")

    def test_does_not_mutate_caller_list(self):
        from twisted.web.resource import Resource
        cred_factories = []
        wrapResource(Resource(), [self.checker], cred_factories)
        assert cred_factories == []

    def test_default_list_not_shared(self):
        from twisted.web.resource import Resource
        first = wrapResource(Resource(), [self.checker])
        second = wrapResource(Resource(), [self.checker])
        assert len(first._credentialFactories) == 1
        assert len(second._credentialFactories) == 1
