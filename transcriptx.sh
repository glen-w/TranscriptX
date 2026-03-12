#!/bin/bash
# transcriptx.sh - Unified TranscriptX launcher with automatic environment setup
# Starts the Streamlit web interface by default.

set -e  # Exit on any error

export CUDA_VISIBLE_DEVICES=""

# Move to the script's directory (project root)
cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[TranscriptX]${NC} $1"; }
print_success() { echo -e "${GREEN}[TranscriptX]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[TranscriptX]${NC} $1"; }
print_error() { echo -e "${RED}[TranscriptX]${NC} $1"; }

write_install_profile() {
    local profile="$1"
    local config_dir="${TRANSCRIPTX_CONFIG_DIR:-$HOME/.config/transcriptx}"
    mkdir -p "$config_dir"
    echo "$profile" > "$config_dir/install_profile"
    print_success "Wrote install_profile=$profile to $config_dir"
}

setup_environment() {
    print_status "Setting up TranscriptX environment..."

    if ! command -v python3.10 &> /dev/null; then
        print_error "Python 3.10 is required but not found."
        echo "Please install Python 3.10 and try again."
        exit 1
    fi

    if [ ! -d ".transcriptx" ]; then
        print_status "Creating Python 3.10 virtual environment..."
        python3.10 -m venv .transcriptx
    fi

    print_status "Activating virtual environment..."
    source .transcriptx/bin/activate

    print_status "Upgrading pip..."
    pip install --upgrade pip

    print_status "Installing setuptools and llvmlite (wheels) for compatibility..."
    pip install "setuptools>=64,<70"
    pip install --prefer-binary "llvmlite>=0.41.0,<0.46" || true

    print_status "Installing numpy (pinned to 1.26.4 for compatibility)..."
    pip install "numpy==1.26.4"

    print_status "Installing compatible spacy and thinc versions..."
    pip install "spacy>=3.7.0,<3.8.0"
    pip install "thinc>=8.2.0,<8.3.0"

    print_status "Installing PyTorch 2.0+ (compatible version)..."
    pip install "torch>=2.0.0"

    print_status "Reinstalling critical ML packages..."
    pip install --force-reinstall --no-deps pyannote.audio
    pip install --force-reinstall --no-deps asteroid-filterbanks

    if [ -f "constraints.txt" ]; then
        pip install -r requirements.txt -c constraints.txt
    else
        pip install -r requirements.txt
    fi

    print_status "Installing transcriptx package in development mode..."
    pip install -e . --use-pep517

    print_status "Installing spaCy models for NER analysis..."
    python -m spacy download en_core_web_sm || true
    python -m spacy download en_core_web_md || true

    write_install_profile "full"
    print_success "Environment setup complete!"
    echo ""
    echo "Start the web interface with: ./transcriptx.sh"
    echo "Open your browser at: http://localhost:8501"
}

setup_environment_core() {
    print_status "Setting up TranscriptX environment (core only)..."
    if ! command -v python3.10 &> /dev/null; then
        print_error "Python 3.10 is required but not found."
        exit 1
    fi
    if [ ! -d ".transcriptx" ]; then
        print_status "Creating Python 3.10 virtual environment..."
        python3.10 -m venv .transcriptx
    fi
    source .transcriptx/bin/activate
    print_status "Upgrading pip..."
    pip install --upgrade pip
    print_status "Installing transcriptx with core dependencies only..."
    pip install -e . --use-pep517
    write_install_profile "core"
    print_success "Core environment setup complete."
}

main() {
    CHECK_EXTRAS=0
    CLEAN_ARGS=()
    for arg in "$@"; do
        if [ "$arg" = "--check-extras" ]; then
            CHECK_EXTRAS=1
        else
            CLEAN_ARGS+=("$arg")
        fi
    done

    if [ ! -f ".transcriptx/bin/activate" ]; then
        if [ -d ".transcriptx" ]; then
            print_warning "Directory .transcriptx exists but is not a valid virtual environment. Recreating..."
            rm -rf .transcriptx
        fi
        if [ "$TRANSCRIPTX_CORE" = "1" ]; then
            print_warning "Virtual environment not found. Setting up core-only environment (TRANSCRIPTX_CORE=1)..."
            setup_environment_core
        else
            print_warning "Virtual environment .transcriptx not found. Setting up environment (full)..."
            setup_environment
        fi
    fi

    print_status "Activating virtual environment (.transcriptx)..."
    source .transcriptx/bin/activate || { print_error "Failed to activate .transcriptx."; exit 1; }
    print_success "Virtual environment activated."
    print_status "Python executable: $(which python)"
    print_status "Python version: $(python --version 2>&1)"

    print_status "Checking transcriptx package installation..."
    PROJECT_ROOT="$(pwd)"
    installed_ok=0
    installed_path="$(python -c "import transcriptx, pathlib; print(pathlib.Path(transcriptx.__file__).resolve())" 2>/dev/null || true)"
    if [ -n "$installed_path" ]; then
        case "$installed_path" in
            "$PROJECT_ROOT"/*) installed_ok=1 ;;
        esac
    fi

    if [ "$installed_ok" -eq 1 ]; then
        print_success "transcriptx package already installed from this project"
    else
        if [ -z "$installed_path" ]; then
            print_warning "transcriptx package not found. Installing in development mode..."
        else
            print_warning "transcriptx package path mismatch. Reinstalling..."
        fi
        pip install -e . --use-pep517
    fi

    print_status "Checking core dependencies..."
    if ! python -c "import streamlit, rich" 2>/dev/null; then
        print_warning "Some dependencies missing. Installing requirements..."
        pip install -r requirements.txt
    else
        print_success "Core dependencies already installed"
    fi

    if [ "$TRANSCRIPTX_CORE" != "1" ] && [ "$TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD" != "1" ]; then
        SPACY_MODEL=$(python -c "from transcriptx.core.utils.nlp_runtime import _resolve_model_name; print(_resolve_model_name(None))" 2>/dev/null) || SPACY_MODEL="en_core_web_md"
        if ! python -c "import spacy; spacy.load('$SPACY_MODEL')" 2>/dev/null; then
            print_status "Installing spaCy model $SPACY_MODEL..."
            python -m spacy download "$SPACY_MODEL" || true
        fi
    fi

    if [ "$CHECK_EXTRAS" -eq 1 ]; then
        print_status "Checking audio processing dependencies..."
        if ! python -c "import pydub" 2>/dev/null; then
            print_warning "pydub not found. Installing pydub..."
            pip install pydub==0.25.1
        else
            print_success "pydub already installed"
        fi
    fi

    HOST="${TRANSCRIPTX_HOST:-127.0.0.1}"
    PORT="${TRANSCRIPTX_PORT:-8501}"

    if [ ${#CLEAN_ARGS[@]} -eq 0 ]; then
        print_status "Starting TranscriptX web interface on http://${HOST}:${PORT} ..."
        exec python -m transcriptx.web --host "$HOST" --port "$PORT"
    else
        print_status "Running TranscriptX with arguments: ${CLEAN_ARGS[*]}"
        exec python -m transcriptx.web "${CLEAN_ARGS[@]}"
    fi
}

main "$@"
