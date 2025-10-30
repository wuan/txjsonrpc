import pytest
from zope.interface import Interface

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse

from txjsonrpc_ng.auth import HTTPAuthRealm, wrapResource


class TestHTTPAuthRealm:

    def setup_method(self):
        self.realm = HTTPAuthRealm("a resource")

    def test_creation(self):
        assert self.realm.resource == "a resource"

    def test_requestAvatarWeb(self):
        from twisted.web.resource import IResource
        interface, resource, logoutMethod = self.realm.requestAvatar(
            "an id", None, IResource)
        assert interface == IResource
        assert resource == self.realm.resource
        assert logoutMethod == self.realm.logout

    def test_requestAvatarNonWeb(self):
        with pytest.raises(NotImplementedError):
            self.realm.requestAvatar("an id", None, [Interface])


class TestWrapResource:

    def setup_method(self):
        self.checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.checker.addUser("joe", "blow")

    def test_wrapResourceWeb(self):
        from twisted.web.resource import IResource, Resource
        root = Resource()
        wrapped = wrapResource(root, [self.checker])
        assert IResource.providedBy(wrapped)
