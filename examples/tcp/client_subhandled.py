import os
import sys

from txjsonrpc_ng import jsonrpclib

sys.path.insert(0, os.getcwd())

from twisted.internet import reactor
from twisted.internet import defer

from txjsonrpc_ng.netstring.jsonrpc import Proxy


def print_value(value):
    print("Result: %s" % str(value))


def print_error(error):
    print('error', error)


def shutdown(data):
    print("Shutting down reactor...")
    reactor.stop()


proxy = Proxy('127.0.0.1', 7080, version=jsonrpclib.VERSION_2)
dl = []

d = proxy.callRemote('system.listMethods')
d.addCallbacks(print_value, print_error)
dl.append(d)

d = proxy.callRemote('echo', 'bite me')
d.addCallbacks(print_value, print_error)
dl.append(d)

d = proxy.callRemote('testing.getList')
d.addCallbacks(print_value, print_error)
dl.append(d)

d = proxy.callRemote('math.add', 3, 5)
d.addCallbacks(print_value, print_error)
dl.append(d)

dl = defer.DeferredList(dl)
dl.addCallback(shutdown)
reactor.run()
