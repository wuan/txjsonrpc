============
Introduction
============

xJsonRpc was forked from txJSON-RPC to create a special purpose python based JSON-RPC server.
It allows you to create async Python JSON-RPC servers and clients
over HTTP.

==========
Motivation
==========

There was a need to cache and compress service responses. If one wants to support the Version and Id fields this is not possible with the known JSON-RPC standard as these values are contained inside the payload.

The proposal here is to transmit these metainformation in the response headers and the payload will be reserved for the service reponse only.

========
Features
========

* Asynchronous JSON-RPC server and client code.

* Support for HTTP JSON-RPC.

* A jsonrpclib similar to the one for XLM-RPC offered by the Python standard
  library.
