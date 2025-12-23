#!/usr/bin/env python3
"""
Test Runner for SQLite Memory Store

This script runs the SQLite memory store tests and provides a summary.
Run this from your project root directory.

Usage:
    python run_sqlite_tests.py              # Run with standard output
    python run_sqlite_tests.py --verbose    # Run with detailed output
    python run_sqlite_tests.py --quick      # Skip performance tests
"""

import subprocess
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Run SQLite Memory Store Tests')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show verbose output')
    parser.add_argument('--quick', '-q', action='store_true',
                       help='Skip performance tests')
    parser.add_argument('--coverage', action='store_true',
                       help='Run with coverage report')
    
    args = parser.parse_args()
    
    # Build pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Test file path
    test_file = 'tests/memory/test_sqlite_store.py'
    
    if args.verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')
    
    if args.quick:
        # Skip performance tests
        cmd.extend(['-k', 'not Performance'])
    
    if args.coverage:
        cmd.extend(['--cov=memory.stores.sqlite', '--cov-report=html'])
    
    cmd.append(test_file)
    
    print("🧪 Running SQLite Memory Store Tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        # Run the tests
        result = subprocess.run(cmd, check=True)
        
        print("-" * 50)
        print("✅ All tests passed!")
        
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/")
        
    except subprocess.CalledProcessError as e:
        print("-" * 50)
        print(f"❌ Tests failed with exit code {e.returncode}")
        sys.exit(1)
    
    except FileNotFoundError:
        print("❌ pytest not found. Install it with: pip install pytest")
        sys.exit(1)


if __name__ == '__main__':
    main()