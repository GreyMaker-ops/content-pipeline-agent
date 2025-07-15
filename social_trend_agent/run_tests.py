#!/usr/bin/env python3
"""
Test runner script for the social trend agent.

This script provides convenient ways to run different types of tests
with proper setup and teardown.
"""

import sys
import os
import asyncio
import argparse
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_command(cmd, cwd=None):
    """Run a shell command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode == 0


def setup_test_environment():
    """Set up the test environment."""
    print("Setting up test environment...")
    
    # Set test environment variables
    os.environ['TESTING'] = 'true'
    os.environ['DATABASE_URL'] = 'sqlite:///test.db'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['LOG_FORMAT'] = 'text'
    
    # Create test directories
    test_dirs = ['logs', 'data', 'media']
    for dir_name in test_dirs:
        os.makedirs(dir_name, exist_ok=True)
    
    print("Test environment ready!")


def cleanup_test_environment():
    """Clean up test environment."""
    print("Cleaning up test environment...")
    
    # Remove test database
    test_db = Path('test.db')
    if test_db.exists():
        test_db.unlink()
    
    # Remove test coverage files
    coverage_files = ['.coverage', 'coverage.xml']
    for file_name in coverage_files:
        file_path = Path(file_name)
        if file_path.exists():
            file_path.unlink()
    
    print("Cleanup complete!")


def run_unit_tests():
    """Run unit tests."""
    print("Running unit tests...")
    cmd = ['python', '-m', 'pytest', 'tests/unit/', '-m', 'unit', '-v']
    return run_command(cmd)


def run_integration_tests():
    """Run integration tests."""
    print("Running integration tests...")
    cmd = ['python', '-m', 'pytest', 'tests/integration/', '-m', 'integration', '-v']
    return run_command(cmd)


def run_all_tests():
    """Run all tests."""
    print("Running all tests...")
    cmd = ['python', '-m', 'pytest', 'tests/', '-v']
    return run_command(cmd)


def run_performance_tests():
    """Run performance tests."""
    print("Running performance tests...")
    cmd = ['python', '-m', 'pytest', 'tests/', '-m', 'performance', '-v']
    return run_command(cmd)


def run_coverage_report():
    """Generate and display coverage report."""
    print("Generating coverage report...")
    
    # Run tests with coverage
    cmd = ['python', '-m', 'pytest', 'tests/', '--cov=trend_graph', '--cov=backend', 
           '--cov-report=term-missing', '--cov-report=html:htmlcov']
    
    if run_command(cmd):
        print("\nCoverage report generated!")
        print("HTML report available at: htmlcov/index.html")
        return True
    else:
        print("Coverage report generation failed!")
        return False


def run_linting():
    """Run code linting."""
    print("Running code linting...")
    
    # Check if flake8 is available
    try:
        import flake8
        cmd = ['python', '-m', 'flake8', 'trend_graph/', 'backend/', 'tests/']
        return run_command(cmd)
    except ImportError:
        print("flake8 not installed, skipping linting")
        return True


def run_type_checking():
    """Run type checking with mypy."""
    print("Running type checking...")
    
    # Check if mypy is available
    try:
        import mypy
        cmd = ['python', '-m', 'mypy', 'trend_graph/', 'backend/']
        return run_command(cmd)
    except ImportError:
        print("mypy not installed, skipping type checking")
        return True


def run_security_check():
    """Run security checks."""
    print("Running security checks...")
    
    # Check if bandit is available
    try:
        import bandit
        cmd = ['python', '-m', 'bandit', '-r', 'trend_graph/', 'backend/']
        return run_command(cmd)
    except ImportError:
        print("bandit not installed, skipping security check")
        return True


def run_full_test_suite():
    """Run the full test suite including linting and type checking."""
    print("Running full test suite...")
    
    success = True
    
    # Setup
    setup_test_environment()
    
    try:
        # Linting
        if not run_linting():
            print("❌ Linting failed!")
            success = False
        else:
            print("✅ Linting passed!")
        
        # Type checking
        if not run_type_checking():
            print("❌ Type checking failed!")
            success = False
        else:
            print("✅ Type checking passed!")
        
        # Security check
        if not run_security_check():
            print("❌ Security check failed!")
            success = False
        else:
            print("✅ Security check passed!")
        
        # Unit tests
        if not run_unit_tests():
            print("❌ Unit tests failed!")
            success = False
        else:
            print("✅ Unit tests passed!")
        
        # Integration tests
        if not run_integration_tests():
            print("❌ Integration tests failed!")
            success = False
        else:
            print("✅ Integration tests passed!")
        
        # Coverage report
        if not run_coverage_report():
            print("❌ Coverage report failed!")
            success = False
        else:
            print("✅ Coverage report generated!")
        
    finally:
        # Cleanup
        cleanup_test_environment()
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test runner for social trend agent')
    parser.add_argument('test_type', nargs='?', default='all',
                       choices=['unit', 'integration', 'all', 'performance', 
                               'coverage', 'lint', 'type', 'security', 'full'],
                       help='Type of tests to run')
    parser.add_argument('--setup-only', action='store_true',
                       help='Only setup test environment')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only cleanup test environment')
    
    args = parser.parse_args()
    
    if args.setup_only:
        setup_test_environment()
        return 0
    
    if args.cleanup_only:
        cleanup_test_environment()
        return 0
    
    # Run tests based on type
    if args.test_type == 'unit':
        setup_test_environment()
        success = run_unit_tests()
        cleanup_test_environment()
        return 0 if success else 1
    
    elif args.test_type == 'integration':
        setup_test_environment()
        success = run_integration_tests()
        cleanup_test_environment()
        return 0 if success else 1
    
    elif args.test_type == 'all':
        setup_test_environment()
        success = run_all_tests()
        cleanup_test_environment()
        return 0 if success else 1
    
    elif args.test_type == 'performance':
        setup_test_environment()
        success = run_performance_tests()
        cleanup_test_environment()
        return 0 if success else 1
    
    elif args.test_type == 'coverage':
        setup_test_environment()
        success = run_coverage_report()
        cleanup_test_environment()
        return 0 if success else 1
    
    elif args.test_type == 'lint':
        return 0 if run_linting() else 1
    
    elif args.test_type == 'type':
        return 0 if run_type_checking() else 1
    
    elif args.test_type == 'security':
        return 0 if run_security_check() else 1
    
    elif args.test_type == 'full':
        return run_full_test_suite()
    
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())

