# txjsonrpc-ng Development Guidelines

## Project Overview

**txjsonrpc-ng** is an asynchronous JSON-RPC library for Python built on Twisted. It provides both server and client implementations supporting:
- JSON-RPC over HTTP
- JSON-RPC over TCP using the Netstring protocol
- Multiple JSON-RPC protocol versions (pre-1.0, 1.0, 2.0)

Package name: `txjsonrpc_ng`
License: BSD, GPL
Minimum Python version: 3.9+

## Architecture

### Core Components

1. **txjsonrpc_ng/jsonrpc.py** - Base classes for JSON-RPC functionality
   - `BaseSubhandler`: Handler hierarchy support with method routing
   - `BaseQueryFactory`: Client-side query handling using Twisted's ClientFactory
   - `BaseProxy`: Base proxy for RPC calls
   - `Introspection`: Built-in introspection support (listMethods, methodHelp, methodSignature)

2. **txjsonrpc_ng/jsonrpclib.py** - JSON-RPC protocol library
   - Protocol version handling
   - Request/response serialization
   - Error handling

3. **txjsonrpc_ng/web/** - HTTP-based JSON-RPC implementation
   - Web server and client components
   - Twisted Web integration

4. **txjsonrpc_ng/netstring/** - TCP-based JSON-RPC using Netstring protocol
   - Direct TCP communication without HTTP overhead

5. **txjsonrpc_ng/auth.py** - Authentication support for JSON-RPC services

### Design Patterns

- **Twisted Deferred**: All async operations use Twisted's Deferred pattern
- **Protocol/Factory pattern**: Follows Twisted's protocol and factory architecture
- **Subhandler pattern**: Allows hierarchical organization of RPC methods with prefixes

## Development Setup

### Prerequisites
- Python 3.9 or higher
- Poetry for dependency management

### Installation

```bash
# Install Poetry if needed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Dependencies

**Runtime:**
- Twisted ^24.11

**Development:**
- assertPy ^1.1 - Assertion library
- pytest ^8.3.3 - Testing framework
- pytest-cov ^5.0.0 - Coverage reporting
- pytest-twisted ^1.14.3 - Twisted integration for pytest
- mock ^5.1.0 - Mocking library
- mypy ^1.12.0 - Static type checking

## Testing

### Running Tests

```bash
# Run all tests with coverage
poetry run pytest --cov txjsonrpc_ng --cov-report xml:reports/coverage.xml --cov-report term --junitxml=reports/junit.xml

# Run specific test file
poetry run pytest tests/test_jsonrpc.py

# Run specific test module
poetry run pytest tests/web/
```

### Test Organization

- `tests/` - Main test directory
- `tests/test_jsonrpc.py` - Core JSON-RPC tests
- `tests/test_jsonrpclib.py` - Library tests
- `tests/test_auth.py` - Authentication tests
- `tests/web/` - HTTP-based JSON-RPC tests
- `tests/netstring/` - Netstring protocol tests

### Coverage Configuration

- Branch coverage is enabled
- Test files (`**/test_*.py`) are omitted from coverage reports
- Target coverage reports to `reports/` directory

## Coding Standards

### Python Style
- Follow PEP 8 guidelines
- Use type hints (enforced by mypy)
- Python 3.9+ features are acceptable

### Type Annotations
- Use type hints for function parameters and return values
- Import types from `typing` module
- Run `mypy` for type checking

### Test Cases
- Use `assertPy` for assertions
- Use `pytest` for testing
  - Use fixtures for common test setup/teardown
- Use `pytest-twisted` for Twisted integration
- Use `mock` for mocking

### Twisted Conventions
- Use `defer.Deferred` for async operations
- Follow Twisted's naming conventions (e.g., `jsonrpc_methodName` for RPC methods)
- Properly handle callbacks and errbacks

### RPC Method Naming
- RPC-exposed methods must be prefixed with `jsonrpc_`
- Example: `def jsonrpc_listMethods(self):`
- This prefix is stripped when the method is called via JSON-RPC

## Building and Distribution

### Build Package

```bash
poetry build
```

This creates both wheel and source distributions in `dist/`.

### Version Management
Version is defined in `pyproject.toml` under `[tool.poetry]`.

## CI/CD

### GitHub Actions
- Workflow: `.github/workflows/build.yml`
- Runs on: Ubuntu and macOS
- Python versions tested: 3.10, 3.11, 3.12, 3.13
- Steps: Install → Test → Build → SonarCloud analysis

### Quality Gates
- **SonarCloud**: Code quality and security analysis
- **OpenSSF Scorecard**: Security best practices
- Coverage reports are generated and sent to SonarCloud

## Examples

Example implementations are in `examples/`:
- `examples/tcp/` - TCP/Netstring examples
- `examples/web/` - HTTP examples
- `examples/ssl/` - SSL-secured examples
- `examples/webAuth/` - Authenticated web examples

## Project Structure Best Practices

### Adding New Features
1. Create/modify module in `txjsonrpc_ng/`
2. Add corresponding tests in `tests/`
3. Add example usage in `examples/` if applicable
4. Update documentation if needed

### Subhandler Implementation
When creating services with subhandlers:
```python
from txjsonrpc_ng.jsonrpc import BaseSubhandler

class MyHandler(BaseSubhandler):
    def jsonrpc_myMethod(self, param):
        # Your implementation
        return result
```

### Client Implementation
When creating clients:
```python
from txjsonrpc_ng.web.jsonrpc import Proxy  # or netstring variant

proxy = Proxy('http://localhost:8080/')
d = proxy.callRemote('methodName', arg1, arg2)
d.addCallback(handleResult)
d.addErrback(handleError)
```

## Common Pitfalls

1. **Forgetting `jsonrpc_` prefix**: Methods won't be exposed without this prefix
2. **Not returning Deferreds**: Async methods must return `defer.Deferred` objects
3. **Blocking operations**: Use Twisted's async alternatives (e.g., `deferToThread`)
4. **Error handling**: Always add errbacks to Deferreds

## Useful Commands

```bash
# Show installed packages
poetry run pip list

# Run specific test with verbose output
poetry run pytest -v tests/test_jsonrpc.py

# Type check with mypy
poetry run mypy txjsonrpc_ng/

# Clean build artifacts
rm -rf dist/ build/ *.egg-info

# Run examples (adjust as needed)
poetry run twistd -noy examples/tcp/server.tac
```

## Resources

- **Twisted Documentation**: https://docs.twistedmatrix.com/
- **JSON-RPC Specification**: See `docs/specs/` for various versions
- **Project History**: See `ChangeLog` and `docs/HISTORY.txt`

## Contributing

When contributing to this project:
1. Ensure all tests pass
2. Maintain or improve test coverage
3. Follow the existing code style
4. Add type hints to new code
5. Update documentation as needed
6. Test on multiple Python versions if possible
