#!/usr/bin/env python3
"""
Deployment verification script for Social Trend Agent.

This script verifies that all components are properly configured
and can be deployed successfully.
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Any

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class DeploymentVerifier:
    """Verifies deployment readiness."""
    
    def __init__(self):
        self.checks = []
        self.errors = []
        self.warnings = []
    
    def add_check(self, name: str, status: bool, message: str = "", warning: bool = False):
        """Add a verification check result."""
        self.checks.append({
            "name": name,
            "status": status,
            "message": message,
            "warning": warning
        })
        
        if not status:
            if warning:
                self.warnings.append(f"{name}: {message}")
            else:
                self.errors.append(f"{name}: {message}")
    
    def verify_file_structure(self) -> None:
        """Verify project file structure."""
        print("🔍 Verifying file structure...")
        
        required_files = [
            "pyproject.toml",
            "README.md",
            ".env.example",
            ".gitignore",
            "docker-compose.yml",
            "docker/Dockerfile",
            "docker/deploy.sh",
            "run_tests.py",
            "pytest.ini"
        ]
        
        required_dirs = [
            "trend_graph",
            "trend_graph/nodes",
            "backend",
            "tests",
            "tests/unit",
            "tests/integration",
            "docker"
        ]
        
        for file_path in required_files:
            exists = Path(file_path).exists()
            self.add_check(
                f"File: {file_path}",
                exists,
                "Missing required file" if not exists else ""
            )
        
        for dir_path in required_dirs:
            exists = Path(dir_path).is_dir()
            self.add_check(
                f"Directory: {dir_path}",
                exists,
                "Missing required directory" if not exists else ""
            )
    
    def verify_python_modules(self) -> None:
        """Verify Python modules can be imported."""
        print("🐍 Verifying Python modules...")
        
        modules_to_check = [
            ("trend_graph.state", "Core state management"),
            ("trend_graph.config", "Configuration management"),
            ("trend_graph.database", "Database module"),
            ("trend_graph.graph", "LangGraph workflow"),
            ("backend.app", "FastAPI application"),
            ("backend.scheduler", "Scheduler module"),
            ("backend.monitoring", "Monitoring module")
        ]
        
        for module_name, description in modules_to_check:
            try:
                __import__(module_name)
                self.add_check(f"Import: {module_name}", True, description)
            except ImportError as e:
                self.add_check(f"Import: {module_name}", False, f"Import error: {e}")
            except Exception as e:
                self.add_check(f"Import: {module_name}", False, f"Error: {e}")
    
    def verify_configuration(self) -> None:
        """Verify configuration files."""
        print("⚙️ Verifying configuration...")
        
        # Check .env.example
        env_example = Path(".env.example")
        if env_example.exists():
            content = env_example.read_text()
            required_vars = [
                "REDDIT_CLIENT_ID",
                "REDDIT_SECRET",
                "TWITTER_API_KEY",
                "TWITTER_API_SECRET",
                "OPENAI_API_KEY"
            ]
            
            for var in required_vars:
                if var in content:
                    self.add_check(f"Env var: {var}", True)
                else:
                    self.add_check(f"Env var: {var}", False, "Missing from .env.example")
        
        # Check pyproject.toml
        pyproject = Path("pyproject.toml")
        if pyproject.exists():
            content = pyproject.read_text()
            required_deps = [
                "fastapi",
                "langgraph",
                "praw",
                "tweepy",
                "openai",
                "tortoise-orm",
                "apscheduler"
            ]
            
            for dep in required_deps:
                if dep in content:
                    self.add_check(f"Dependency: {dep}", True)
                else:
                    self.add_check(f"Dependency: {dep}", False, "Missing from pyproject.toml")
    
    def verify_docker_setup(self) -> None:
        """Verify Docker configuration."""
        print("🐳 Verifying Docker setup...")
        
        # Check Dockerfile
        dockerfile = Path("docker/Dockerfile")
        if dockerfile.exists():
            content = dockerfile.read_text()
            
            checks = [
                ("FROM", "Base image specified"),
                ("WORKDIR", "Working directory set"),
                ("COPY", "Files copied"),
                ("EXPOSE", "Port exposed"),
                ("CMD", "Command specified")
            ]
            
            for keyword, description in checks:
                if keyword in content:
                    self.add_check(f"Dockerfile: {keyword}", True, description)
                else:
                    self.add_check(f"Dockerfile: {keyword}", False, f"Missing {keyword}")
        
        # Check docker-compose.yml
        compose_file = Path("docker-compose.yml")
        if compose_file.exists():
            content = compose_file.read_text()
            
            if "trend-agent" in content:
                self.add_check("Docker Compose: Service defined", True)
            else:
                self.add_check("Docker Compose: Service defined", False, "No trend-agent service")
            
            if "ports:" in content:
                self.add_check("Docker Compose: Ports mapped", True)
            else:
                self.add_check("Docker Compose: Ports mapped", False, "No port mapping")
    
    def verify_tests(self) -> None:
        """Verify test configuration."""
        print("🧪 Verifying test setup...")
        
        # Check pytest.ini
        pytest_ini = Path("pytest.ini")
        if pytest_ini.exists():
            content = pytest_ini.read_text()
            
            if "testpaths" in content:
                self.add_check("Pytest: Test paths configured", True)
            else:
                self.add_check("Pytest: Test paths configured", False, "No testpaths in pytest.ini")
            
            if "asyncio_mode" in content:
                self.add_check("Pytest: Async mode configured", True)
            else:
                self.add_check("Pytest: Async mode configured", False, "No asyncio_mode in pytest.ini")
        
        # Check test files
        test_files = [
            "tests/conftest.py",
            "tests/unit/test_state.py",
            "tests/unit/test_scoring.py",
            "tests/integration/test_workflow.py"
        ]
        
        for test_file in test_files:
            exists = Path(test_file).exists()
            self.add_check(
                f"Test file: {test_file}",
                exists,
                "Missing test file" if not exists else ""
            )
    
    def verify_scripts(self) -> None:
        """Verify executable scripts."""
        print("📜 Verifying scripts...")
        
        scripts = [
            "run_tests.py",
            "docker/deploy.sh",
            "docker/update.sh",
            "docker/entrypoint.sh"
        ]
        
        for script in scripts:
            script_path = Path(script)
            if script_path.exists():
                is_executable = os.access(script_path, os.X_OK)
                self.add_check(
                    f"Script: {script}",
                    is_executable,
                    "Not executable" if not is_executable else "Executable"
                )
            else:
                self.add_check(f"Script: {script}", False, "Missing script")
    
    def verify_documentation(self) -> None:
        """Verify documentation completeness."""
        print("📚 Verifying documentation...")
        
        readme = Path("README.md")
        if readme.exists():
            content = readme.read_text()
            
            sections = [
                "Features",
                "Architecture",
                "Prerequisites",
                "Quick Start",
                "API Documentation",
                "Configuration",
                "Testing",
                "Monitoring",
                "Docker Deployment",
                "Troubleshooting"
            ]
            
            for section in sections:
                if section in content:
                    self.add_check(f"README: {section} section", True)
                else:
                    self.add_check(f"README: {section} section", False, f"Missing {section} section", warning=True)
        else:
            self.add_check("README.md", False, "Missing README.md file")
    
    def run_syntax_check(self) -> None:
        """Run Python syntax check."""
        print("🔍 Running syntax check...")
        
        python_files = []
        for pattern in ["**/*.py"]:
            python_files.extend(Path(".").glob(pattern))
        
        syntax_errors = 0
        for py_file in python_files:
            if "/.venv/" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                with open(py_file, 'r') as f:
                    compile(f.read(), py_file, 'exec')
            except SyntaxError as e:
                self.add_check(f"Syntax: {py_file}", False, f"Syntax error: {e}")
                syntax_errors += 1
            except Exception as e:
                self.add_check(f"Syntax: {py_file}", False, f"Error: {e}")
                syntax_errors += 1
        
        if syntax_errors == 0:
            self.add_check("Python syntax", True, f"Checked {len(python_files)} files")
        else:
            self.add_check("Python syntax", False, f"{syntax_errors} files with syntax errors")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate verification report."""
        passed = sum(1 for check in self.checks if check["status"])
        total = len(self.checks)
        
        report = {
            "summary": {
                "total_checks": total,
                "passed": passed,
                "failed": total - passed,
                "warnings": len(self.warnings),
                "success_rate": (passed / total * 100) if total > 0 else 0
            },
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings
        }
        
        return report
    
    def print_report(self, report: Dict[str, Any]) -> None:
        """Print verification report."""
        summary = report["summary"]
        
        print("\n" + "="*60)
        print("🔍 DEPLOYMENT VERIFICATION REPORT")
        print("="*60)
        
        print(f"Total Checks: {summary['total_checks']}")
        print(f"Passed: {summary['passed']} ✅")
        print(f"Failed: {summary['failed']} ❌")
        print(f"Warnings: {summary['warnings']} ⚠️")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        if report["errors"]:
            print("\n❌ ERRORS:")
            for error in report["errors"]:
                print(f"  • {error}")
        
        if report["warnings"]:
            print("\n⚠️ WARNINGS:")
            for warning in report["warnings"]:
                print(f"  • {warning}")
        
        print("\n📋 DETAILED RESULTS:")
        for check in report["checks"]:
            status = "✅" if check["status"] else ("⚠️" if check["warning"] else "❌")
            message = f" - {check['message']}" if check["message"] else ""
            print(f"  {status} {check['name']}{message}")
        
        print("\n" + "="*60)
        
        if summary["failed"] == 0:
            print("🎉 ALL CHECKS PASSED! Ready for deployment.")
        else:
            print("💥 SOME CHECKS FAILED! Please fix errors before deployment.")
        
        print("="*60)


def main():
    """Main verification function."""
    print("🚀 Starting deployment verification...")
    
    verifier = DeploymentVerifier()
    
    # Run all verification checks
    verifier.verify_file_structure()
    verifier.verify_python_modules()
    verifier.verify_configuration()
    verifier.verify_docker_setup()
    verifier.verify_tests()
    verifier.verify_scripts()
    verifier.verify_documentation()
    verifier.run_syntax_check()
    
    # Generate and print report
    report = verifier.generate_report()
    verifier.print_report(report)
    
    # Save report to file
    with open("verification_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: verification_report.json")
    
    # Return exit code
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

