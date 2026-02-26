#!/bin/bash
# transcriptx.sh - Unified TranscriptX launcher with automatic environment setup

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

# Function to print colored output
print_status() {
    echo -e "${BLUE}[TranscriptX]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[TranscriptX]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[TranscriptX]${NC} $1"
}

print_error() {
    echo -e "${RED}[TranscriptX]${NC} $1"
}

# Write install profile marker for deterministic core_mode resolution (~/.config/transcriptx/install_profile)
write_install_profile() {
    local profile="$1"
    local config_dir="${TRANSCRIPTX_CONFIG_DIR:-$HOME/.config/transcriptx}"
    mkdir -p "$config_dir"
    echo "$profile" > "$config_dir/install_profile"
    print_success "Wrote install_profile=$profile to $config_dir"
}

# Function to setup environment (full install)
setup_environment() {
    print_status "Setting up TranscriptX environment..."
    
    # Check if Python 3.10 is available
    if ! command -v python3.10 &> /dev/null; then
        print_error "Python 3.10 is required but not found."
        echo "Please install Python 3.10 and try again."
        exit 1
    fi

    # Create virtual environment if it doesn't exist
    if [ ! -d ".transcriptx" ]; then
        print_status "Creating Python 3.10 virtual environment..."
        python3.10 -m venv .transcriptx
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source .transcriptx/bin/activate

    # Upgrade pip
    print_status "Upgrading pip..."
    pip install --upgrade pip

    # Avoid llvmlite build failure: use setuptools<70 and prefer llvmlite wheel
    print_status "Installing setuptools and llvmlite (wheels) for compatibility..."
    pip install "setuptools>=64,<70"
    pip install --prefer-binary "llvmlite>=0.41.0,<0.46" || true

    # Install numpy first (pinned to 1.26.4 for compatibility with ML modules)
    print_status "Installing numpy (pinned to 1.26.4 for compatibility)..."
    pip install "numpy==1.26.4"

    # Install compatible spacy and thinc versions
    print_status "Installing compatible spacy and thinc versions..."
    pip install "spacy>=3.7.0,<3.8.0"
    pip install "thinc>=8.2.0,<8.3.0"

    # Install PyTorch 2.0+ (compatible version)
    print_status "Installing PyTorch 2.0+ (compatible version)..."
    pip install "torch>=2.0.0"

    # Force reinstall critical ML packages for compatibility
    print_status "Reinstalling critical ML packages..."
    pip install --force-reinstall --no-deps pyannote.audio
    pip install --force-reinstall --no-deps asteroid-filterbanks

    # Install enhanced error handling and user feedback dependencies
    print_status "Installing enhanced error handling and user feedback dependencies..."
    pip install "psutil>=5.9.0"  # System resource monitoring
    pip install "tqdm>=4.65.0"  # Progress bars with percentage
    pip install "click>=8.1.0"  # Enhanced CLI utilities
    pip install "python-dotenv>=1.0.0"  # Environment variable management
    pip install "structlog>=23.1.0"  # Structured logging
    pip install "tenacity>=8.2.0"  # Retry logic with exponential backoff
    pip install "watchdog>=3.0.0"  # File system monitoring for large processes
    pip install "humanize>=4.7.0"  # Human-readable file sizes and durations
    pip install "alive-progress>=3.1.0"  # Advanced progress bars
    pip install "prompt-toolkit>=3.0.0"  # Enhanced input handling
    pip install "keyring>=24.0.0"  # Secure credential storage
    pip install "cryptography>=41.0.0"  # Security utilities
    pip install "pydantic>=2.0.0"  # Data validation and settings management
    pip install "pydantic-settings>=2.0.0"  # Settings management
    pip install "cerberus>=1.3.0"  # Data validation
    pip install "marshmallow>=3.20.0"  # Serialization and validation
    pip install "jsonschema>=4.17.0"  # JSON schema validation

    # Install all other dependencies (use constraints so build isolation gets setuptools<70)
    print_status "Installing remaining dependencies..."
    if [ -f "constraints.txt" ]; then
        pip install -r requirements.txt -c constraints.txt
    else
        pip install -r requirements.txt
    fi

    # Install transcriptx package in development mode (after dependencies)
    print_status "Installing transcriptx package in development mode..."
    pip install -e . --use-pep517

    # Install spaCy models for NER analysis
    print_status "Installing spaCy models for NER analysis..."
    python -m spacy download en_core_web_sm  # Lightweight model (optional)
    python -m spacy download en_core_web_md  # Medium model (default)

    # Verify spaCy models
    print_status "Verifying spaCy models..."
    python -c "
import spacy
try:
    nlp_sm = spacy.load('en_core_web_sm')
    print('✅ Lightweight spaCy model (en_core_web_sm) installed')
except OSError:
    print('❌ Lightweight spaCy model not available')
try:
    nlp_md = spacy.load('en_core_web_md')
    print('✅ Medium spaCy model (en_core_web_md) installed')
except OSError:
    print('❌ Medium spaCy model not available')
"

    # Verify enhanced dependencies
    print_status "Verifying enhanced dependencies..."
    python -c "
try:
    import psutil
    print(f'✅ psutil version: {psutil.__version__}')
except ImportError:
    print('❌ psutil not available')

try:
    import tqdm
    print(f'✅ tqdm version: {tqdm.__version__}')
except ImportError:
    print('❌ tqdm not available')

try:
    import tenacity
    print(f'✅ tenacity version: {tenacity.__version__}')
except ImportError:
    print('❌ tenacity not available')

try:
    import pydantic
    print(f'✅ pydantic version: {pydantic.__version__}')
except ImportError:
    print('❌ pydantic not available')

try:
    import alive_progress
    print('✅ alive-progress available')
except ImportError:
    print('❌ alive-progress not available')

try:
    import humanize
    print(f'✅ humanize version: {humanize.__version__}')
except ImportError:
    print('❌ humanize not available')
"

    # Verify installation
    print_status "Verifying installation..."
    python -c "
import torch
import transformers
import numpy as np
import spacy
import thinc
print(f'✅ PyTorch version: {torch.__version__}')
print(f'✅ Transformers version: {transformers.__version__}')
print(f'✅ NumPy version: {np.__version__}')
print(f'✅ spaCy version: {spacy.__version__}')
print(f'✅ thinc version: {thinc.__version__}')
try:
    import streamlit
    print(f'✅ Streamlit version: {streamlit.__version__} (web interface available)')
except ImportError:
    print('⚠️  Streamlit not available (web interface will not work)')
print('✅ All core dependencies installed successfully!')
"

    write_install_profile "full"
    print_success "Environment setup complete!"
    echo ""
    echo "✨ Enhanced Features Available:"
    echo "  🛡️  Comprehensive error handling with graceful recovery"
    echo "  📊 Real-time progress tracking with percentage completion"
    echo "  🔄 Automatic retry logic with exponential backoff"
    echo "  💾 Resource monitoring and memory management"
    echo "  ⏰ Timeout handling for long-running operations"
    echo "  🎯 User-friendly error messages and feedback"
    echo "  🚪 Graceful exit handling with Ctrl+C support"
    echo "  🌐 Streamlit web interface (transcriptx web-viewer)"
    echo ""
}

# Core-only install when TRANSCRIPTX_CORE=1 (minimal deps, no torch/spacy/pyannote/etc.)
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

# Main execution logic
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

    # Check for virtual environment
    if [ ! -d ".transcriptx" ]; then
        if [ "$TRANSCRIPTX_CORE" = "1" ]; then
            print_warning "Virtual environment not found. Setting up core-only environment (TRANSCRIPTX_CORE=1)..."
            setup_environment_core
        else
            print_warning "Virtual environment .transcriptx not found. Setting up environment (full)..."
            setup_environment
        fi
    fi

    # Activate the virtual environment
    print_status "Activating virtual environment (.transcriptx)..."
    source .transcriptx/bin/activate || { print_error "Failed to activate .transcriptx."; exit 1; }
    print_success "Virtual environment activated."
    print_status "Python executable: $(which python)"
    print_status "Python version: $(python --version 2>&1)"
    print_status "VIRTUAL_ENV: $VIRTUAL_ENV"

    # Check if transcriptx package is installed
    print_status "Checking transcriptx package installation..."
    PROJECT_ROOT="$(pwd)"
    installed_ok=0
    installed_path="$(python -c "import transcriptx, pathlib; print(pathlib.Path(transcriptx.__file__).resolve())" 2>/dev/null || true)"
    if [ -n "$installed_path" ]; then
        case "$installed_path" in
            "$PROJECT_ROOT"/*)
                installed_ok=1
                ;;
        esac
    fi

    if [ "$installed_ok" -eq 1 ]; then
        print_success "transcriptx package already installed from this project"
    else
        if [ -z "$installed_path" ]; then
            print_warning "transcriptx package not found. Installing in development mode..."
        else
            print_warning "transcriptx package path mismatch:"
            print_warning "  installed: $installed_path"
            print_warning "  expected under: $PROJECT_ROOT/"
            print_warning "Reinstalling transcriptx in development mode from this project..."
        fi
        pip install -e . --use-pep517
    fi

    # Check if core dependencies are installed
    print_status "Checking core dependencies..."
    if ! python -c "import questionary, typer, rich, textblob, nrclex" 2>/dev/null; then
        print_warning "Core dependencies missing. Installing requirements..."
        pip install -r requirements.txt
    else
        print_success "Core dependencies already installed"
    fi

    # Ensure default spaCy model when not in core mode and auto-download not disabled
    if [ "$TRANSCRIPTX_CORE" = "1" ] || [ "$TRANSCRIPTX_DISABLE_SPACY_DOWNLOAD" = "1" ]; then
        SPACY_MODEL=$(python -c "from transcriptx.core.utils.nlp_runtime import _resolve_model_name; print(_resolve_model_name(None))" 2>/dev/null) || SPACY_MODEL="en_core_web_md"
        print_warning "To install the spaCy model manually: python -m spacy download $SPACY_MODEL"
    else
        SPACY_MODEL=$(python -c "from transcriptx.core.utils.nlp_runtime import _resolve_model_name; print(_resolve_model_name(None))" 2>/dev/null) || SPACY_MODEL="en_core_web_md"
        if ! python -c "import spacy; spacy.load('$SPACY_MODEL')" 2>/dev/null; then
            print_status "Installing spaCy model $SPACY_MODEL (required for NLP analysis)..."
            python -m spacy download "$SPACY_MODEL" || true
        fi
    fi

    if [ "$CHECK_EXTRAS" -eq 1 ]; then
        # Optional dependency checks (extras)
        print_status "Checking Streamlit (web interface)..."
        if ! python -c "import streamlit" 2>/dev/null; then
            print_warning "Streamlit not found. Installing streamlit>=1.29.0..."
            pip install "streamlit>=1.29.0"
        else
            streamlit_version=$(python -c "import streamlit; print(streamlit.__version__)" 2>/dev/null || echo "unknown")
            print_success "Streamlit already installed (version: $streamlit_version)"
        fi

        # Check if pydub is installed (required for WAV processing)
        print_status "Checking audio processing dependencies..."
        if ! python -c "import pydub" 2>/dev/null; then
            print_warning "pydub not found. Installing pydub..."
            pip install pydub==0.25.1
        else
            print_success "pydub already installed"
        fi

        # Check for spaCy models
        print_status "Checking spaCy models..."
        if [ -f "scripts/archived/check_spacy_models.py" ]; then
            python scripts/archived/check_spacy_models.py
        else
            print_warning "check_spacy_models.py not found, skipping model check"
        fi
    fi

    # Suppress macOS MallocStackLogging notice (overlays speaker UI, harmless)
    # stderr is filtered so only that line is dropped; other errors still show
    run_python() {
        python "$@" 2> >(grep -v 'MallocStackLogging' >&2)
    }

    # If no arguments, launch interactive CLI; else, pass arguments to CLI
    if [ ${#CLEAN_ARGS[@]} -eq 0 ]; then
        print_status "Starting TranscriptX interactive CLI..."
        run_python -m transcriptx.cli.main interactive
    else
        print_status "Running TranscriptX with arguments: ${CLEAN_ARGS[*]}"
        run_python -m transcriptx.cli.main "${CLEAN_ARGS[@]}"
    fi
}

# Run main function with all arguments
main "$@" 