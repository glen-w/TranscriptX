#!/usr/bin/env python3
"""
spaCy Model Checker for TranscriptX
Verifies that required spaCy models are installed and working.
"""

import sys
import subprocess


def check_spacy_installation():
    """Check if spaCy is installed."""
    try:
        import spacy

        print(f"✅ spaCy version: {spacy.__version__}")
        return True
    except ImportError:
        print("❌ spaCy not installed")
        return False


def check_model(model_name, description=""):
    """Check if a specific spaCy model is installed and working."""
    try:
        import spacy

        nlp = spacy.load(model_name)
        print(f"✅ {model_name} - {description}")

        # Test basic functionality
        doc = nlp("This is a test sentence.")
        if len(doc) > 0:
            print("   ✓ Model working correctly")
        else:
            print("   ⚠️  Model loaded but not processing text")
        return True
    except OSError:
        print(f"❌ {model_name} - {description} (not installed)")
        return False
    except Exception as e:
        print(f"❌ {model_name} - {description} (error: {e})")
        return False


def install_model(model_name, description=""):
    """Install a spaCy model."""
    print(f"📦 Installing {model_name}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✅ {model_name} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {model_name}: {e}")
        return False


def main():
    """Main function to check and install spaCy models."""
    print("🔍 Checking spaCy models for TranscriptX...")
    print("=" * 50)

    # Check spaCy installation
    if not check_spacy_installation():
        print("\n❌ spaCy is not installed. Please install it first:")
        print("   pip install spacy")
        return False

    print()

    # Define required models
    models = [
        ("en_core_web_sm", "Small English model (recommended)"),
        ("en_core_web_md", "Medium English model (fallback)"),
    ]

    missing_models = []

    # Check each model
    for model_name, description in models:
        if not check_model(model_name, description):
            missing_models.append((model_name, description))

    print()

    # Install missing models if any
    if missing_models:
        print(f"📦 Installing {len(missing_models)} missing model(s)...")
        print()

        for model_name, description in missing_models:
            if install_model(model_name, description):
                # Verify installation
                check_model(model_name, description)
            print()
    else:
        print("✅ All required spaCy models are installed and working!")

    # Final verification
    print("🔍 Final verification...")
    all_good = True
    for model_name, description in models:
        if not check_model(model_name, description):
            all_good = False

    if all_good:
        print("\n🎉 All spaCy models are ready for TranscriptX!")
        return True
    else:
        print("\n❌ Some models are still not working properly.")
        print("   You may need to reinstall spaCy or the models manually.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
