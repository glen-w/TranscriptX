#!/bin/bash

# TranscriptX Documentation Builder
# This script builds and tests the Sphinx documentation

set -e  # Exit on any error

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

# Check if we're in the right directory
if [ ! -f "docs/conf.py" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check if pip is available
    if ! command -v pip &> /dev/null; then
        print_error "pip is required but not installed"
        exit 1
    fi
    
    # Check if make is available
    if ! command -v make &> /dev/null; then
        print_error "make is required but not installed"
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

# Function to install documentation dependencies
install_docs_deps() {
    print_status "Installing documentation dependencies..."
    
    if pip install -r docs/requirements.txt; then
        print_success "Documentation dependencies installed"
    else
        print_error "Failed to install documentation dependencies"
        exit 1
    fi
}

# Function to generate API documentation
generate_api_docs() {
    print_status "Generating API documentation..."
    
    cd docs
    
    if make apidoc; then
        print_success "API documentation generated"
    else
        print_warning "API documentation generation failed, continuing..."
    fi
    
    cd ..
}

# Function to build HTML documentation
build_html() {
    print_status "Building HTML documentation..."
    
    cd docs
    
    if make html; then
        print_success "HTML documentation built successfully"
    else
        print_error "Failed to build HTML documentation"
        exit 1
    fi
    
    cd ..
}

# Function to build all documentation formats
build_all() {
    print_status "Building all documentation formats..."
    
    cd docs
    
    if make all; then
        print_success "All documentation formats built successfully"
    else
        print_error "Failed to build all documentation formats"
        exit 1
    fi
    
    cd ..
}

# Function to check for broken links
check_links() {
    print_status "Checking for broken links..."
    
    cd docs
    
    if make linkcheck; then
        print_success "Link check completed"
    else
        print_warning "Link check found issues"
    fi
    
    cd ..
}

# Function to spell check
spell_check() {
    print_status "Running spell check..."
    
    cd docs
    
    if make spelling; then
        print_success "Spell check completed"
    else
        print_warning "Spell check found issues"
    fi
    
    cd ..
}

# Function to serve documentation locally
serve_docs() {
    print_status "Starting documentation server..."
    
    cd docs
    
    if make serve; then
        print_success "Documentation server started at http://localhost:8000"
    else
        print_error "Failed to start documentation server"
        exit 1
    fi
    
    cd ..
}

# Function to clean build directory
clean_build() {
    print_status "Cleaning build directory..."
    
    cd docs
    
    if make clean; then
        print_success "Build directory cleaned"
    else
        print_warning "Failed to clean build directory"
    fi
    
    cd ..
}

# Function to show help
show_help() {
    echo "TranscriptX Documentation Builder"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  install     Install documentation dependencies"
    echo "  build       Build HTML documentation"
    echo "  build-all   Build all documentation formats (HTML, PDF, EPUB)"
    echo "  api         Generate API documentation"
    echo "  links       Check for broken links"
    echo "  spell       Run spell check"
    echo "  serve       Serve documentation locally"
    echo "  clean       Clean build directory"
    echo "  full        Full build (install, api, build, links, spell)"
    echo "  dev         Development build with warnings as errors"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 install     # Install dependencies"
    echo "  $0 build       # Build HTML docs"
    echo "  $0 serve       # Start local server"
    echo "  $0 full        # Complete build process"
}

# Main script logic
case "${1:-help}" in
    install)
        check_dependencies
        install_docs_deps
        ;;
    build)
        check_dependencies
        build_html
        ;;
    build-all)
        check_dependencies
        build_all
        ;;
    api)
        check_dependencies
        generate_api_docs
        ;;
    links)
        check_dependencies
        check_links
        ;;
    spell)
        check_dependencies
        spell_check
        ;;
    serve)
        check_dependencies
        serve_docs
        ;;
    clean)
        clean_build
        ;;
    full)
        check_dependencies
        install_docs_deps
        generate_api_docs
        build_html
        check_links
        spell_check
        print_success "Full documentation build completed"
        ;;
    dev)
        check_dependencies
        cd docs
        if make dev; then
            print_success "Development build completed"
        else
            print_error "Development build failed"
            exit 1
        fi
        cd ..
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac

print_success "Documentation build script completed successfully!" 