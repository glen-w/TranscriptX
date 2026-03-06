#!/bin/bash

# TranscriptX Dependency Management Script
# This script provides comprehensive dependency management with validation and safety checks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment is active
check_venv() {
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        print_error "Virtual environment not active. Please activate .transcriptx first."
        print_status "Run: source .transcriptx/bin/activate"
        exit 1
    fi
    print_success "Virtual environment active: $VIRTUAL_ENV"
}

# Validate dependency versions
validate_dependencies() {
    print_status "Validating dependency versions..."
    
    # Check critical ML dependencies
    python -c "
import sys
import pkg_resources

critical_deps = {
    'numpy': '1.26.4',
    'torch': '2.2.2',
    'transformers': '4.54.0',
    'spacy': '3.7.5',
    'pandas': '2.3.0'
}

issues = []
for package, expected_version in critical_deps.items():
    try:
        installed_version = pkg_resources.get_distribution(package).version
        if installed_version != expected_version:
            issues.append(f'{package}: expected {expected_version}, got {installed_version}')
    except pkg_resources.DistributionNotFound:
        issues.append(f'{package}: not installed')

if issues:
    print('❌ Version mismatches found:')
    for issue in issues:
        print(f'  - {issue}')
    sys.exit(1)
else:
    print('✅ All critical dependencies match expected versions')
"
}

# Generate lock file
generate_lock_file() {
    print_status "Generating lock file..."
    pip freeze > requirements-lock.txt
    print_success "Lock file generated: requirements-lock.txt"
}

# Install dependencies with validation
install_dependencies() {
    print_status "Installing dependencies from requirements.txt..."
    
    # Install with strict version checking
    pip install -r requirements.txt --no-deps
    
    # Install dependencies for each package
    pip install -r requirements.txt
    
    print_success "Dependencies installed successfully"
}

# Check for security vulnerabilities
check_security() {
    print_status "Checking for security vulnerabilities..."
    
    # Check if safety is installed
    if ! command -v safety &> /dev/null; then
        print_warning "safety not installed. Installing..."
        pip install safety
    fi
    
    # Run security check
    safety scan -r requirements.txt || {
        print_warning "Security vulnerabilities found. Check the output above."
        return 1
    }
    
    print_success "No security vulnerabilities found"
}

# Update dependencies safely
update_dependencies() {
    print_status "Updating dependencies safely..."
    
    # Create backup of current lock file
    cp requirements-lock.txt requirements-lock.txt.backup
    
    # Update non-critical dependencies first
    print_status "Updating non-critical dependencies..."
    pip install --upgrade pip setuptools wheel
    
    # Update utilities and non-ML packages
    pip install --upgrade click python-dotenv structlog tenacity watchdog humanize
    
    # Generate new lock file
    generate_lock_file
    
    # Validate after update
    validate_dependencies
    
    print_success "Dependencies updated successfully"
}

# Clean up old packages
cleanup_packages() {
    print_status "Cleaning up unused packages..."
    
    # Remove packages not in requirements
    pip uninstall -y $(pip freeze | grep -v -f requirements.txt | cut -d'=' -f1) || true
    
    print_success "Cleanup completed"
}

# Show dependency status
show_status() {
    print_status "Current dependency status:"
    
    echo ""
    echo "📦 Critical ML Dependencies:"
    python -c "
import pkg_resources
critical = ['numpy', 'torch', 'transformers', 'spacy', 'pandas']
for pkg in critical:
    try:
        version = pkg_resources.get_distribution(pkg).version
        print(f'  {pkg}: {version}')
    except:
        print(f'  {pkg}: NOT INSTALLED')
"
    
    echo ""
    echo "🔒 Lock file status:"
    if [ -f "requirements-lock.txt" ]; then
        echo "  ✅ requirements-lock.txt exists"
        echo "  📅 Last modified: $(stat -f "%Sm" requirements-lock.txt)"
    else
        echo "  ❌ requirements-lock.txt missing"
    fi
    
    echo ""
    echo "🐍 Python environment:"
    echo "  Python: $(python --version)"
    echo "  pip: $(pip --version)"
    echo "  Virtual env: $VIRTUAL_ENV"
}

# Main function
main() {
    case "${1:-help}" in
        "install")
            check_venv
            install_dependencies
            validate_dependencies
            generate_lock_file
            ;;
        "validate")
            check_venv
            validate_dependencies
            ;;
        "update")
            check_venv
            update_dependencies
            ;;
        "security")
            check_venv
            check_security
            ;;
        "cleanup")
            check_venv
            cleanup_packages
            ;;
        "status")
            check_venv
            show_status
            ;;
        "lock")
            check_venv
            generate_lock_file
            ;;
        "help"|*)
            echo "🚀 TranscriptX Dependency Management"
            echo "=================================="
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  install   - Install all dependencies with validation"
            echo "  validate  - Validate current dependency versions"
            echo "  update    - Update dependencies safely"
            echo "  security  - Check for security vulnerabilities"
            echo "  cleanup   - Remove unused packages"
            echo "  status    - Show current dependency status"
            echo "  lock      - Generate lock file from current environment"
            echo "  help      - Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 install    # Install and validate all dependencies"
            echo "  $0 status     # Check current dependency status"
            echo "  $0 security   # Run security vulnerability check"
            ;;
    esac
}

# Run main function
main "$@" 