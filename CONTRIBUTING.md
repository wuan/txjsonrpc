# Contributing to txjsonrpc-ng

Thank you for your interest in contributing to txjsonrpc-ng! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

## Code of Conduct

This project adheres to a code of conduct that all contributors are expected to follow. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) for dependency management
- Git

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/txjsonrpc.git
cd txjsonrpc
```

2. **Install Poetry** (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. **Install dependencies**

```bash
poetry install
```

4. **Activate the virtual environment**

```bash
poetry shell
```

5. **Install pre-commit hooks** (recommended)

```bash
poetry run pre-commit install
```

## Making Changes

### Branch Naming

Create a descriptive branch for your changes:

- `feature/your-feature-name` - for new features
- `fix/issue-description` - for bug fixes
- `docs/what-you-document` - for documentation changes
- `refactor/what-you-refactor` - for code refactoring

Example:
```bash
git checkout -b feature/add-batch-request-support
```

### Commit Messages

Write clear, descriptive commit messages:

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Start with a capital letter
- Limit the first line to 72 characters
- Reference issues and pull requests when relevant

Example:
```
Add batch request support for JSON-RPC 2.0

- Implement batch request handling in jsonrpclib
- Add tests for batch operations
- Update documentation

Fixes #123
```

## Testing

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov txjsonrpc_ng --cov-report term

# Run specific test file
poetry run pytest tests/test_jsonrpc.py

# Run specific test
poetry run pytest tests/test_jsonrpc.py::TestClassName::test_method_name

# Run with verbose output
poetry run pytest -v
```

### Writing Tests

- Write tests for all new functionality
- Ensure all tests pass before submitting a pull request
- Aim for high test coverage (check existing coverage with `pytest --cov`)
- Use descriptive test names that explain what is being tested
- Follow the existing test structure and patterns

Test files should be in the `tests/` directory and named `test_*.py`.

Example:
```python
import pytest
from twisted.trial import unittest
from txjsonrpc_ng.web.jsonrpc import Handler

class TestMyFeature(unittest.TestCase):
    def test_my_feature_does_something(self):
        """Test that my feature behaves correctly"""
        # Arrange
        handler = Handler()
        
        # Act
        result = handler.my_feature()
        
        # Assert
        self.assertEqual(result, expected_value)
```

## Code Style

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for function parameters and return values
- Maximum line length: 88 characters (Black default)
- Use meaningful variable and function names

### Type Hints

Add type hints to all new code:

```python
from typing import Dict, List, Optional, Any
from twisted.internet import defer

def process_request(data: Dict[str, Any]) -> defer.Deferred[str]:
    """Process a JSON-RPC request."""
    ...
```

### Docstrings

Use docstrings for modules, classes, and functions:

```python
def jsonrpc_myMethod(self, param: str) -> str:
    """
    Brief description of what the method does.
    
    Args:
        param: Description of the parameter
        
    Returns:
        Description of the return value
        
    Raises:
        ValueError: When input is invalid
    """
    ...
```

### Code Formatting

The project uses pre-commit hooks for automatic code formatting:

- **Black**: Code formatter
- **isort**: Import sorter
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with a newline

Run manually:
```bash
poetry run pre-commit run --all-files
```

### Type Checking

Run mypy for type checking:

```bash
poetry run mypy txjsonrpc_ng/
```

Fix any type errors before submitting.

## Submitting Changes

### Pull Request Process

1. **Update your branch**

```bash
git checkout main
git pull origin main
git checkout your-branch
git rebase main
```

2. **Run all checks**

```bash
# Run tests
poetry run pytest --cov txjsonrpc_ng

# Run type checking
poetry run mypy txjsonrpc_ng/

# Run pre-commit hooks
poetry run pre-commit run --all-files
```

3. **Push your changes**

```bash
git push origin your-branch
```

4. **Create a Pull Request**

- Go to the GitHub repository
- Click "New Pull Request"
- Select your branch
- Fill in the PR template with:
  - Description of changes
  - Related issue numbers
  - Testing performed
  - Any breaking changes

5. **Address Review Comments**

- Respond to reviewer feedback
- Make requested changes
- Push updates to the same branch

### Pull Request Checklist

Before submitting, ensure:

- [ ] All tests pass
- [ ] Code is formatted (Black, isort)
- [ ] Type hints are added
- [ ] Documentation is updated
- [ ] IMPROVEMENTS.md is updated if applicable
- [ ] Commit messages are clear
- [ ] No merge conflicts with main branch

## Reporting Bugs

### Before Reporting

1. Check if the bug has already been reported in [Issues](https://github.com/wuan/txjsonrpc/issues)
2. Test with the latest version from the main branch
3. Gather information about the bug

### Creating a Bug Report

Include:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Minimal steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**:
  - Python version
  - txjsonrpc-ng version
  - Twisted version
  - Operating system
- **Code Sample**: Minimal code to reproduce (if applicable)
- **Traceback**: Full error traceback (if applicable)

## Requesting Features

### Feature Request Guidelines

When requesting a feature:

1. Check if it's already been requested or implemented
2. Explain the use case and why it would be valuable
3. Provide examples of how it would be used
4. Consider if it fits within the project's scope

### Implementing Features

If you want to implement a feature:

1. Open an issue first to discuss the approach
2. Wait for maintainer feedback before starting work
3. Follow the development workflow above
4. Include tests and documentation

## Project Structure

```
txjsonrpc/
├── txjsonrpc_ng/          # Main package
│   ├── jsonrpc.py         # Core JSON-RPC functionality
│   ├── jsonrpclib.py      # Protocol library
│   ├── auth.py            # Authentication
│   ├── web/               # HTTP implementation
│   └── netstring/         # TCP/Netstring implementation
├── tests/                 # Test suite
│   ├── test_jsonrpc.py
│   ├── web/
│   └── netstring/
├── examples/              # Usage examples
├── docs/                  # Documentation
└── pyproject.toml         # Project configuration
```

## RPC Method Naming Convention

Methods exposed via JSON-RPC must be prefixed with `jsonrpc_`:

```python
class MyHandler(BaseSubhandler):
    def jsonrpc_myMethod(self, param):
        """This method will be exposed as 'myMethod' via JSON-RPC"""
        return result
    
    def _helper_method(self):
        """This method is private and not exposed"""
        pass
```

## Twisted Conventions

- Use `defer.Deferred` for asynchronous operations
- Return Deferreds from async methods
- Always add errbacks to handle errors
- Don't use blocking operations - use Twisted's async alternatives

Example:
```python
from twisted.internet import defer

def jsonrpc_asyncOperation(self):
    """Async operation using Deferreds"""
    d = defer.Deferred()
    
    def callback(result):
        # Process result
        return processed_result
    
    def errback(failure):
        # Handle error
        return failure
    
    d.addCallback(callback)
    d.addErrback(errback)
    
    return d
```

## Getting Help

- **Documentation**: See `docs/` directory and examples in `examples/`
- **Issues**: Browse or create [GitHub Issues](https://github.com/wuan/txjsonrpc/issues)
- **Discussions**: For questions and discussions (if enabled)

## License

By contributing, you agree that your contributions will be licensed under the project's BSD/GPL license.

## Thank You!

Your contributions make txjsonrpc-ng better for everyone. We appreciate your time and effort!
