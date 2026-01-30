#!/bin/bash

# Test script for Docker setup
# This script verifies that the Docker environment is working correctly

set -e

echo "🧪 Testing TranscriptX Docker Setup..."

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

# Test 1: Check if Docker is running
test_docker_running() {
    print_status "Test 1: Checking Docker availability..."
    if docker info > /dev/null 2>&1; then
        print_success "Docker is running"
        return 0
    else
        print_error "Docker is not running"
        return 1
    fi
}

# Test 2: Check if docker-compose files exist
test_compose_files() {
    print_status "Test 2: Checking docker-compose files..."
    
    if [ -f "docker-compose.yml" ]; then
        print_success "docker-compose.yml exists"
    else
        print_error "docker-compose.yml missing"
        return 1
    fi
    
    if [ -f "docker-compose.full.yml" ]; then
        print_success "docker-compose.full.yml exists"
    else
        print_error "docker-compose.full.yml missing"
        return 1
    fi
    
    return 0
}

# Test 3: Check if Docker images can be built
test_image_build() {
    print_status "Test 3: Testing Docker image build..."
    
    # Test development image build
    if docker build --target development -t transcriptx:test-dev . > /dev/null 2>&1; then
        print_success "Development image builds successfully"
    else
        print_error "Development image build failed"
        return 1
    fi
    
    # Test production image build
    if docker build --target production -t transcriptx:test-prod . > /dev/null 2>&1; then
        print_success "Production image builds successfully"
    else
        print_error "Production image build failed"
        return 1
    fi
    
    # Clean up test images
    docker rmi transcriptx:test-dev transcriptx:test-prod > /dev/null 2>&1 || true
    
    return 0
}

# Test 4: Check if convenience scripts exist
test_scripts() {
    print_status "Test 4: Checking convenience scripts..."
    
    scripts=("docker-dev.sh" "docker-prod.sh" "docker-web.sh" "docker-test.sh" "docker-docs.sh" "docker-full.sh" "docker-clean.sh")
    
    for script in "${scripts[@]}"; do
        if [ -f "scripts/$script" ] && [ -x "scripts/$script" ]; then
            print_success "scripts/$script exists and is executable"
        else
            print_error "scripts/$script missing or not executable"
            return 1
        fi
    done
    
    return 0
}

# Test 5: Check if directories exist
test_directories() {
    print_status "Test 5: Checking data directories..."
    
    directories=("data" "outputs" "transcriptx_output" "test_data")
    
    for dir in "${directories[@]}"; do
        if [ -d "$dir" ]; then
            print_success "Directory $dir exists"
        else
            print_warning "Directory $dir missing (will be created by setup)"
        fi
    done
    
    return 0
}

# Test 6: Validate docker-compose syntax
test_compose_syntax() {
    print_status "Test 6: Validating docker-compose syntax..."
    
    if docker-compose -f docker-compose.yml config > /dev/null 2>&1; then
        print_success "docker-compose.yml syntax is valid"
    else
        print_error "docker-compose.yml syntax is invalid"
        return 1
    fi
    
    if docker-compose -f docker-compose.full.yml config > /dev/null 2>&1; then
        print_success "docker-compose.full.yml syntax is valid"
    else
        print_error "docker-compose.full.yml syntax is invalid"
        return 1
    fi
    
    return 0
}

# Main test execution
main() {
    echo "🚀 TranscriptX Docker Setup Test"
    echo "================================"
    echo ""
    
    tests=(
        test_docker_running
        test_compose_files
        test_image_build
        test_scripts
        test_directories
        test_compose_syntax
    )
    
    passed=0
    total=${#tests[@]}
    
    for test in "${tests[@]}"; do
        if $test; then
            ((passed++))
        fi
        echo ""
    done
    
    echo "📊 Test Results: $passed/$total tests passed"
    echo ""
    
    if [ $passed -eq $total ]; then
        print_success "🎉 All tests passed! Docker setup is ready."
        echo ""
        echo "Next steps:"
        echo "  ./scripts/docker-full.sh    - Start full environment"
        echo "  ./scripts/docker-dev.sh     - Start development environment"
        echo "  ./scripts/docker-web.sh     - Start web viewer"
    else
        print_error "❌ Some tests failed. Please check the errors above."
        echo ""
        echo "Troubleshooting:"
        echo "  1. Make sure Docker is running"
        echo "  2. Run ./scripts/docker-setup.sh to setup the environment"
        echo "  3. Check file permissions on scripts/"
        exit 1
    fi
}

# Run main function
main "$@" 