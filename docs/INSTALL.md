# Installation

## Requirements

- Python 3.10+
- Twisted 24.11+

## From PyPI

Using pip:

```bash
pip install txjsonrpc-ng
```

Using Poetry:

```bash
poetry add txjsonrpc-ng
```

## From Source

Clone the repository and install:

```bash
git clone https://github.com/wuan/txjsonrpc.git
cd txjsonrpc
poetry install
```

## Running Tests

```bash
poetry run pytest
```

Or with coverage:

```bash
poetry run pytest --cov txjsonrpc_ng --cov-report html
```
