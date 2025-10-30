#!/usr/bin/env python
"""
Pytest-based doctest runner for txjsonrpc-ng documentation.

This script runs doctests from documentation files using pytest.
It can be run directly or via pytest.

Usage:
    # Run directly
    python admin/testDocs.py

    # Run via pytest
    pytest admin/testDocs.py -v
"""
import sys
import pytest
from pathlib import Path


def main():
    """Run doctests using pytest."""
    # Get the project root directory (parent of admin/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Collect all doctest files
    doctest_files = list(project_root.glob("docs/specs/*.txt"))
    doctest_files.append(project_root / "docs/USAGE.txt")
    
    # Convert to strings for pytest
    doctest_paths = [str(f) for f in doctest_files]
    
    # Run pytest with doctest options
    pytest_args = [
        "--doctest-glob=*.txt",
        "-v",
        *doctest_paths
    ]
    
    return pytest.main(pytest_args)


if __name__ == '__main__':
    sys.exit(main())
