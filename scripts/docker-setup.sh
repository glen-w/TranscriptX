#!/bin/bash

# TranscriptX Docker Setup Script
# This script sets up the WhisperX Docker service for TranscriptX

set -e

echo "🐳 Setting up TranscriptX WhisperX Docker service..."

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

# Check if Docker is running
check_docker() {
    print_status "Checking Docker availability..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p data/recordings data/transcripts data/outputs
    print_success "Directories created"
}

# Start WhisperX service
start_whisperx() {
    print_status "Starting WhisperX service..."
    docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx
    if [ $? -eq 0 ]; then
        print_success "WhisperX service started"
    else
        print_error "Failed to start WhisperX service"
        exit 1
    fi
}

# Test the setup
test_setup() {
    print_status "Testing WhisperX service..."
    sleep 2
    if docker ps | grep -q transcriptx-whisperx; then
        print_success "WhisperX container is running"
    else
        print_warning "WhisperX container may not be running - check with: docker ps"
    fi
}

# Show usage instructions
show_instructions() {
    echo ""
    echo "🎉 WhisperX Docker setup complete!"
    echo ""
    echo "📋 Available commands:"
    echo "  docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx  - Start WhisperX service"
    echo "  docker-compose -f docker-compose.whisperx.yml --profile whisperx down            - Stop WhisperX service"
    echo "  docker-compose -f docker-compose.whisperx.yml --profile whisperx logs -f whisperx  - View logs"
    echo ""
    echo "📁 Data directories:"
    echo "  ./data/recordings/        - Input audio files"
    echo "  ./data/transcripts/        - Output transcripts"
    echo "  ./data/outputs/           - Analysis outputs"
    echo ""
    echo "💡 Usage:"
    echo "  1. Start WhisperX service: docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx"
    echo "  2. Use CLI locally: ./transcriptx.sh"
    echo "  3. CLI will automatically detect and use the WhisperX service"
    echo ""
}

# Main execution
main() {
    echo "🚀 TranscriptX WhisperX Docker Setup"
    echo "===================================="
    echo ""
    
    check_docker
    create_directories
    start_whisperx
    test_setup
    show_instructions
}

# Run main function
main "$@" 