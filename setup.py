#!/usr/bin/env python3
"""
Setup script for TCRS Document Processor Azure Function

This script helps with initial setup and validation of the development environment.
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.11+"""
    version = sys.version_info
    if version.major != 3 or version.minor < 11:
        print(f"❌ Python 3.11+ required, found {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_azure_functions_core_tools():
    """Check if Azure Functions Core Tools is installed"""
    try:
        result = subprocess.run(['func', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Azure Functions Core Tools: {version}")
            if not version.startswith('4.'):
                print("⚠️  Warning: Azure Functions Core Tools 4.x recommended")
            return True
        else:
            print("❌ Azure Functions Core Tools not found")
            return False
    except FileNotFoundError:
        print("❌ Azure Functions Core Tools not found")
        print("   Install with: npm install -g azure-functions-core-tools@4 --unsafe-perm true")
        return False


def create_local_settings():
    """Create local.settings.json from template if it doesn't exist"""
    local_settings_path = Path("local.settings.json")
    template_path = Path("local.settings.example.json")

    if local_settings_path.exists():
        print("✅ local.settings.json already exists")
        return True

    if not template_path.exists():
        print("❌ local.settings.example.json template not found")
        return False

    try:
        with open(template_path, 'r') as f:
            template_content = json.load(f)

        with open(local_settings_path, 'w') as f:
            json.dump(template_content, f, indent=2)

        print("✅ Created local.settings.json from template")
        print("⚠️  Please update local.settings.json with your Azure configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create local.settings.json: {e}")
        return False


def install_dependencies():
    """Install Python dependencies"""
    try:
        print("📦 Installing Python dependencies...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False


def run_tests():
    """Run the test suite"""
    try:
        print("🧪 Running tests...")
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/unit/', '-v'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ All tests passed")
            print(result.stdout)
            return True
        else:
            print(f"❌ Some tests failed:\n{result.stdout}\n{result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def validate_environment():
    """Validate environment variables"""
    required_vars = [
        'AZURE_STORAGE_CONNECTION_STRING',
        'BLOB_CONTAINER_NAME',
        'TCRS_API_BASE_URL',
        'INTERNAL_FUNCTION_KEY'
    ]

    missing_vars = []

    # Check if local.settings.json exists and read from it
    local_settings_path = Path("local.settings.json")
    if local_settings_path.exists():
        try:
            with open(local_settings_path, 'r') as f:
                settings = json.load(f)
                values = settings.get('Values', {})

                for var in required_vars:
                    if var not in values or not values[var] or values[var].startswith('your_'):
                        missing_vars.append(var)
        except Exception as e:
            print(f"❌ Error reading local.settings.json: {e}")
            return False
    else:
        missing_vars = required_vars

    if missing_vars:
        print(f"⚠️  Missing or incomplete environment variables in local.settings.json:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    else:
        print("✅ All required environment variables configured")
        return True


def main():
    """Main setup function"""
    print("🚀 TCRS Document Processor Setup")
    print("=" * 50)

    checks_passed = 0
    total_checks = 6

    # Check Python version
    if check_python_version():
        checks_passed += 1

    # Check Azure Functions Core Tools
    if check_azure_functions_core_tools():
        checks_passed += 1

    # Create local settings
    if create_local_settings():
        checks_passed += 1

    # Install dependencies
    if install_dependencies():
        checks_passed += 1

    # Validate environment
    if validate_environment():
        checks_passed += 1

    # Run tests
    if run_tests():
        checks_passed += 1

    print("\n" + "=" * 50)
    print(f"Setup Summary: {checks_passed}/{total_checks} checks passed")

    if checks_passed == total_checks:
        print("🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Update local.settings.json with your Azure configuration")
        print("2. Start the function: func start")
        print("3. Test with: curl -X POST http://localhost:7071/api/process-documents -H \"Content-Type: application/json\" -d @test_request.json")
    else:
        print("❌ Setup incomplete. Please address the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()