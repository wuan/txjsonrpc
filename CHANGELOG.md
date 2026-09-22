# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.2] - 2026-09-23

### Fixed
- Cached `CacheableResult` renderings are now keyed by the JSON-RPC version and
  request id.  Previously the first request to populate a cache entry fixed the
  response envelope (and the echoed id) for every later cache hit, so a legacy
  pre-1.0 request could make subsequent v1/v2 requests receive the bare-array
  envelope.

## [Unreleased]

### Added
- ``JSONRPC.treat_zero_id_as_pre1``: opt-in support for non-conforming legacy
  pre-1.0 clients that send a fixed ``id`` of ``0`` but expect the bare-array
  pre-1.0 response envelope.  The spec-correct JSON-RPC 1.0 interpretation
  remains the default.

### Fixed
- **Security**: `auth` results are now enforced by `requires_auth`; a falsy
  return value denies the request instead of executing the method anyway.
- **Security**: JSONP callback state is now stored per request, preventing a
  concurrent request from injecting its callback into another response.
- Invalid or malformed JSON-RPC requests no longer raise unhandled exceptions
  (HTTP 500); they return a proper JSON-RPC fault.
- Anonymous (`params: null`) and named parameters are handled correctly.
- A JSON-RPC 1.0 `id` of `0` is no longer mistaken for a pre-1.0 request.
- Pre-1.0 responses with falsy results (`0`, `false`, `""`, `[]`, `{}`) no
  longer collapse to `null`.
- JSON-RPC 2.0 responses containing `"error": null` parse successfully.
- Unknown methods over the netstring transport return a fault instead of
  raising out of the protocol handler.
- Query factories now generate unique request ids.
- `wrapResource` no longer mutates its arguments or shares default state.

## [0.8.1] - 2024-10-31

### Changed
- Version bump to 0.8.1.

## [0.8.0] - 2024-10-31

### Added
- CI type checking with mypy
- Code of Conduct (Contributor Covenant v2.0)
- CONTRIBUTING.md guidelines
- SECURITY.md policy
- Issue and PR templates

### Changed
- Minimum Python version updated to 3.10
- Documentation converted to Markdown format

### Fixed
- Type annotations for mypy compatibility

## [0.7.4] - 2024-10-29

### Changed
- Updated dependencies

## [0.7.3] - 2024-09-03

### Changed
- Updated dependencies

## [0.7.2] - 2024-10-28

### Changed
- Updated dependencies

## [0.7.1] - 2024-10-14

### Changed
- Updated dependencies

## [0.7.0] - 2024-10-14

### Changed
- Updated to use txjsonrpc-ng package name
- Updated dependencies

## [0.4] - 2021-06-01

### Changed
- Removed web2 support
- Updated JSON support for modern Python versions
- Fixed setup.py bug in source distribution

## [0.3.1] - 2015-05-25

### Fixed
- Setup.py bug fix

## [0.3.0] - 2015-XX-XX

### Changed
- Removed twisted.web2 dependency for TCP/Netstring code
- Allow setting MAX_LENGTH attribute for Netstring JSON-RPC

## [0.2.0] - 2015-XX-XX

### Added
- Datetime serializer

## [0.1.0] - 2015-XX-XX

### Fixed
- SimpleParser bug fix for long replies (Moshe Zadka)

## [0.0.5] - 2015-XX-XX

### Fixed
- SimpleParser bug fix
- Improved code abstractions

## [0.0.4] - 2015-XX-XX

### Changed
- Renamed to txJSON-RPC per Twisted community recommendations
