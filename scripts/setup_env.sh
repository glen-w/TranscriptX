#!/bin/bash

# TranscriptX Environment Setup Script
# Choose your deployment environment

set -e

echo "🚀 TranscriptX Environment Setup"
echo "=================================="
echo ""

# Check if Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found."
    echo "Please install Python 3.10+ and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created at .venv/"
else
    echo "✅ Virtual environment already exists at .venv/"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Function to install Playwright browsers if playwright is installed
install_playwright_browsers() {
    if python -c "import playwright" 2>/dev/null; then
        echo "🌐 Installing Playwright browsers (required for NER location maps)..."
        python -m playwright install chromium || {
            echo "⚠️  Warning: Failed to install Playwright browsers. You may need to run 'python -m playwright install chromium' manually."
        }
    fi
}

install_mpv() {
    if command -v mpv &> /dev/null; then
        return
    fi

    echo ""
    read -p "Install mpv for fast audio segment playback? (y/N): " install_mpv_choice
    if [[ ! "$install_mpv_choice" =~ ^[Yy]$ ]]; then
        echo "ℹ️  Skipping mpv install. You can install later for faster playback."
        return
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            echo "🎵 Installing mpv via Homebrew..."
            brew install mpv || {
                echo "⚠️  Warning: mpv install failed. You can install manually: brew install mpv"
            }
        else
            echo "⚠️  Homebrew not found. Install mpv manually: https://mpv.io/installation/"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            echo "🎵 Installing mpv via apt..."
            sudo apt-get update && sudo apt-get install -y mpv || {
                echo "⚠️  Warning: mpv install failed. You can install manually: sudo apt-get install mpv"
            }
        elif command -v dnf &> /dev/null; then
            echo "🎵 Installing mpv via dnf..."
            sudo dnf install -y mpv || {
                echo "⚠️  Warning: mpv install failed. You can install manually: sudo dnf install mpv"
            }
        elif command -v pacman &> /dev/null; then
            echo "🎵 Installing mpv via pacman..."
            sudo pacman -S --noconfirm mpv || {
                echo "⚠️  Warning: mpv install failed. You can install manually: sudo pacman -S mpv"
            }
        else
            echo "⚠️  Unsupported Linux package manager. Install mpv manually: https://mpv.io/installation/"
        fi
    else
        echo "⚠️  Unsupported OS for automatic mpv install. Install manually: https://mpv.io/installation/"
    fi
}

echo ""
echo "Choose your deployment environment:"
echo "1. Core CLI (minimal dependencies - fast startup)"
echo "2. Full ML (all dependencies - complete functionality)"
echo "3. Web Frontend (lightweight web viewer)"
echo "4. Development (with dev tools and testing)"
echo "5. Docker Core (minimal container)"
echo "6. Docker Full (complete container)"
echo "7. Docker Web (web viewer container)"
echo ""

read -p "Enter your choice (1-7): " choice

case $choice in
    1)
        echo "📦 Installing Core CLI dependencies..."
        pip install -r requirements.txt
        install_playwright_browsers
        install_mpv
        echo "✅ Core CLI environment ready!"
        echo "💡 Use: transcriptx --help"
        echo "💡 Web viewer: transcriptx web-viewer"
        echo "💡 To activate: source .venv/bin/activate"
        ;;
    2)
        echo "🤖 Installing Full ML dependencies..."
        pip install -r requirements.txt
        install_playwright_browsers
        install_mpv
        echo "✅ Full ML environment ready!"
        echo "💡 Use: transcriptx --help"
        echo "💡 Web viewer: transcriptx web-viewer"
        echo "💡 To activate: source .venv/bin/activate"
        ;;
    3)
        echo "⚠️  Web Frontend option removed. Use option 1 or 2 instead."
        echo "💡 To activate: source .venv/bin/activate"
        ;;
    4)
        echo "🔧 Installing Development environment..."
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        install_playwright_browsers
        install_mpv
        echo "✅ Development environment ready!"
        echo "💡 Use: pytest for testing"
        echo "💡 Web viewer: transcriptx web-viewer"
        echo "💡 To activate: source .venv/bin/activate"
        ;;
    5)
        echo "🐳 Starting Docker Core environment..."
        docker-compose -f docker-compose.core.yml --profile core up -d
        echo "✅ Docker Core environment ready!"
        echo "💡 Use: docker exec -it transcriptx-core bash"
        ;;
    6)
        echo "🐳 Starting Docker Full environment..."
        docker-compose --profile prod up -d
        echo "✅ Docker Full environment ready!"
        echo "💡 Use: docker exec -it transcriptx-prod bash"
        ;;
    7)
        echo "🐳 Starting Docker Web environment..."
        docker-compose --profile web up -d
        echo "✅ Docker Web environment ready!"
        echo "💡 Web viewer available at: http://localhost:8000"
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "🎉 Setup complete! Check the documentation for usage examples."
echo ""
echo "📝 To activate the virtual environment in the future:"
echo "   source .venv/bin/activate"
echo ""
echo "📝 To deactivate the virtual environment:"
echo "   deactivate" 