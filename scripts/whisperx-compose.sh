#!/bin/bash

# WhisperX Docker Compose Management Script
# This script helps manage the WhisperX Docker Compose service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Load local WhisperX env if present (local-only, gitignored)
if [ -f "./whisperx.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "./whisperx.env"
    set +a
fi

# Function to print colored output
print_status() {
    echo -e "${CYAN}[INFO]${NC} $1"
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

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if Docker Compose is available
check_compose() {
    if ! command -v docker-compose > /dev/null 2>&1; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
}

# Function to start WhisperX service
start_whisperx() {
    print_status "Starting WhisperX service..."
    
    # Check if service is already running
    if docker ps --filter name=transcriptx-whisperx --format "{{.Names}}" | grep -q "transcriptx-whisperx"; then
        print_warning "WhisperX service is already running."
        return 0
    fi
    
    # Start the service
    if docker-compose --profile whisperx up -d whisperx; then
        print_success "WhisperX service started successfully!"
        print_status "Service is running in the background."
        print_status "You can check logs with: docker logs transcriptx-whisperx"
    else
        print_error "Failed to start WhisperX service."
        exit 1
    fi
}

# Function to stop WhisperX service
stop_whisperx() {
    print_status "Stopping WhisperX service..."
    
    if docker-compose --profile whisperx down; then
        print_success "WhisperX service stopped successfully!"
    else
        print_error "Failed to stop WhisperX service."
        exit 1
    fi
}

# Function to restart WhisperX service
restart_whisperx() {
    print_status "Restarting WhisperX service..."
    stop_whisperx
    sleep 2
    start_whisperx
}

# Function to check service status
status_whisperx() {
    print_status "Checking WhisperX service status..."
    
    if docker ps --filter name=transcriptx-whisperx --format "{{.Names}}" | grep -q "transcriptx-whisperx"; then
        print_success "WhisperX service is running."
        print_status "Container details:"
        docker ps --filter name=transcriptx-whisperx --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        print_warning "WhisperX service is not running."
    fi
}

# Function to show logs
logs_whisperx() {
    print_status "Showing WhisperX service logs..."
    docker logs transcriptx-whisperx
}

# Function to run a transcription
transcribe() {
    if [ -z "$1" ]; then
        print_error "Please provide an audio file path."
        print_status "Usage: $0 transcribe <audio_file>"
        exit 1
    fi
    
    if [ ! -f "$1" ]; then
        print_error "Audio file not found: $1"
        exit 1
    fi
    
    # Check if service is running
    if ! docker ps --filter name=transcriptx-whisperx --format "{{.Names}}" | grep -q "transcriptx-whisperx"; then
        print_warning "WhisperX service is not running. Starting it now..."
        start_whisperx
    fi
    
    print_status "Running transcription for: $1"
    
    # Copy file to data directory if needed
    audio_filename=$(basename "$1")
    if [ ! -f "./data/$audio_filename" ]; then
        print_status "Copying audio file to data directory..."
        mkdir -p ./data
        cp "$1" "./data/$audio_filename"
    fi
    
    # Run transcription
    hf_args=()
    if [ -n "${HF_TOKEN:-}" ]; then
        hf_args=(--hf_token "$HF_TOKEN")
    else
        print_warning "HF_TOKEN not set; diarization may fail or run without diarization."
    fi

    docker exec transcriptx-whisperx whisperx \
        "/data/input/$audio_filename" \
        --output_dir /data/output \
        --output_format json \
        --model large-v2 \
        --language en \
        --compute_type float16 \
        --device cpu \
        --diarize \
        "${hf_args[@]}"
    
    if [ $? -eq 0 ]; then
        print_success "Transcription completed!"
        print_status "Output files are in: ./outputs/"
    else
        print_error "Transcription failed."
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "WhisperX Docker Compose Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start       Start the WhisperX service"
    echo "  stop        Stop the WhisperX service"
    echo "  restart     Restart the WhisperX service"
    echo "  status      Check the status of the WhisperX service"
    echo "  logs        Show logs from the WhisperX service"
    echo "  transcribe  Run transcription on an audio file"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 transcribe /path/to/audio.wav"
    echo "  $0 logs"
}

# Main script logic
main() {
    # Check prerequisites
    check_docker
    check_compose
    
    # Parse command
    case "${1:-help}" in
        start)
            start_whisperx
            ;;
        stop)
            stop_whisperx
            ;;
        restart)
            restart_whisperx
            ;;
        status)
            status_whisperx
            ;;
        logs)
            logs_whisperx
            ;;
        transcribe)
            transcribe "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
