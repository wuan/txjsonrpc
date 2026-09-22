from twisted import web
from twisted.cred.portal import IRealm, Portal
from twisted.web import guard
from zope.interface import implementer


@implementer(IRealm)
class HTTPAuthRealm(object):

    def __init__(self, resource):
        self.resource = resource

    def logout(self):
        pass

    def requestAvatar(self, avatarId, mind, *interfaces):
        if web.resource.IResource in interfaces:
            return web.resource.IResource, self.resource, self.logout
        raise NotImplementedError()


def wrapResource(resource, checkers, credFactories=None, realmName=""):
    # Never mutate a caller-provided list and never share the default across
    # calls (the previous ``credFactories=[]`` default accumulated factories).
    credFactories = list(credFactories) if credFactories else []
    defaultCredFactory = guard.BasicCredentialFactory(realmName)
    credFactories.insert(0, defaultCredFactory)
    realm = HTTPAuthRealm(resource)
    portal = Portal(realm, checkers)
    return guard.HTTPAuthSessionWrapper(portal, credFactories)
