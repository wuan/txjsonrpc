# Usage

## Examples

The `examples/` directory contains:

- **HTTP-based JSON-RPC**: `examples/web/`
- **TCP/Netstring JSON-RPC**: `examples/tcp/`
- **SSL-secured JSON-RPC**: `examples/ssl/`
- **Authenticated JSON-RPC**: `examples/webAuth/`

Examine the Python files in these directories to understand how to use txjsonrpc-ng.

## Quick Start

### HTTP Server

```python
from twisted.web import server
from twisted.internet import reactor
from txjsonrpc_ng.web.jsonrpc import Handler

class ExampleHandler(Handler):
    def jsonrpc_echo(self, message):
        return message

if __name__ == '__main__':
    r = ExampleHandler()
    reactor.listenTCP(8080, server.Site(r))
    reactor.run()
```

### HTTP Client

```python
from twisted.internet import reactor
from txjsonrpc_ng.web.jsonrpc import Proxy

def handleResult(result):
    print("Result:", result)
    reactor.stop()

proxy = Proxy('http://localhost:8080/')
d = proxy.callRemote('echo', 'Hello!')
d.addCallback(handleResult)
reactor.run()
```
