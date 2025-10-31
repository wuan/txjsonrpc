============
txjsonrpc-ng
============

.. image:: https://img.shields.io/pypi/v/txjsonrpc-ng.svg
    :alt: PyPI version
    :target: https://pypi.org/project/txjsonrpc-ng/

.. image:: https://img.shields.io/pypi/pyversions/txjsonrpc-ng.svg
    :alt: Python versions
    :target: https://pypi.org/project/txjsonrpc-ng/

.. image:: https://img.shields.io/github/license/wuan/txjsonrpc.svg
    :alt: License
    :target: https://github.com/wuan/txjsonrpc/blob/main/LICENSE

.. image:: https://sonarcloud.io/api/project_badges/measure?project=wuan_txjsonrpc&metric=alert_status
    :alt: Quality gate
    :target: https://sonarcloud.io/project/overview?id=wuan_txjsonrpc

.. image:: https://sonarcloud.io/api/project_badges/measure?project=wuan_txjsonrpc&metric=coverage
    :alt: Coverage
    :target: https://sonarcloud.io/project/overview?id=wuan_txjsonrpc

.. image:: https://sonarcloud.io/api/project_badges/measure?project=wuan_txjsonrpc&metric=reliability_rating
    :alt: Reliability rating
    :target: https://sonarcloud.io/project/overview?id=wuan_txjsonrpc

.. image:: https://api.scorecard.dev/projects/github.com/wuan/txjsonrpc/badge
    :alt: OpenSSF Scorecard
    :target: https://scorecard.dev/viewer/?uri=github.com/wuan/txjsonrpc

------------
Introduction
------------

**txjsonrpc-ng** is an asynchronous JSON-RPC library for Python built on Twisted. It allows you to create async Python JSON-RPC servers and clients either over HTTP or directly on TCP with the Netstring protocol.

--------
Features
--------

* 🚀 **Asynchronous**: Built on Twisted for high-performance async I/O
* 🌐 **Multiple Transports**: HTTP and TCP (Netstring) support
* 📋 **Protocol Versions**: Supports JSON-RPC pre-1.0, 1.0, and 2.0
* 🔒 **Authentication**: Built-in authentication support
* 🔍 **Introspection**: Built-in method introspection (listMethods, methodHelp, methodSignature)
* 📚 **jsonrpclib**: Similar to Python's xmlrpclib for easy migration

------------
Installation
------------

Install from PyPI using pip:

.. code-block:: bash

    pip install txjsonrpc-ng

Or using Poetry:

.. code-block:: bash

    poetry add txjsonrpc-ng

Requirements:

* Python 3.10 or higher
* Twisted 24.11 or higher

-----------
Quick Start
-----------

**Server Example (HTTP)**

.. code-block:: python

    from twisted.web import server
    from twisted.internet import reactor
    from txjsonrpc_ng.web.jsonrpc import Handler

    class ExampleHandler(Handler):
        def jsonrpc_echo(self, message):
            """Echo the message back"""
            return message
        
        def jsonrpc_add(self, a, b):
            """Add two numbers"""
            return a + b

    if __name__ == '__main__':
        r = ExampleHandler()
        reactor.listenTCP(8080, server.Site(r))
        print("JSON-RPC server running on http://localhost:8080/")
        reactor.run()

**Client Example (HTTP)**

.. code-block:: python

    from twisted.internet import reactor
    from txjsonrpc_ng.web.jsonrpc import Proxy

    def printResult(result):
        print("Result:", result)
        reactor.stop()

    def printError(error):
        print("Error:", error)
        reactor.stop()

    if __name__ == '__main__':
        proxy = Proxy('http://localhost:8080/')
        d = proxy.callRemote('add', 5, 3)
        d.addCallback(printResult)
        d.addErrback(printError)
        reactor.run()

--------
Examples
--------

More examples are available in the ``examples/`` directory:

* ``examples/web/`` - HTTP-based JSON-RPC
* ``examples/tcp/`` - TCP/Netstring-based JSON-RPC
* ``examples/ssl/`` - SSL-secured JSON-RPC
* ``examples/webAuth/`` - Authenticated JSON-RPC

-------------
Documentation
-------------

* **Installation**: See ``docs/INSTALL.txt``
* **Usage Guide**: See ``docs/USAGE.txt``
* **Specifications**: See ``docs/specs/`` for JSON-RPC protocol versions
* **Contributing**: See ``CONTRIBUTING.md``
* **Security**: See ``SECURITY.md``

-------
License
-------

txjsonrpc-ng is licensed under BSD and GPL. See ``LICENSE`` for details.

------------
Contributing
------------

Contributions are welcome! Please see ``CONTRIBUTING.md`` for guidelines.

-------
Support
-------

* **Issues**: `GitHub Issues <https://github.com/wuan/txjsonrpc/issues>`_
* **Source**: `GitHub Repository <https://github.com/wuan/txjsonrpc>`_
