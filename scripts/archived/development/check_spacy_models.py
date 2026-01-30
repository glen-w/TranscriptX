#!/usr/bin/env python3
"""
Check and install spaCy models for TranscriptX NER analysis.
This script ensures the required spaCy models are available.
"""

import subprocess
import sys

import spacy


def check_model(model_name):
    """Check if a spaCy model is available."""
    try:
        spacy.load(model_name)
        print(f"✅ {model_name} is available")
        return True
    except OSError:
        print(f"❌ {model_name} is not available")
        return False


def install_model(model_name):
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
    print("🔍 Checking spaCy models for TranscriptX NER analysis...")

    models = ["en_core_web_sm", "en_core_web_md"]
    missing_models = []

    for model in models:
        if not check_model(model):
            missing_models.append(model)

    if missing_models:
        print(f"\n📦 Installing missing models: {', '.join(missing_models)}")
        for model in missing_models:
            install_model(model)

        # Verify installation
        print("\n🔍 Verifying installation...")
        for model in models:
            check_model(model)
    else:
        print("\n✅ All required spaCy models are available!")

    print("\n🎉 spaCy model check complete!")


if __name__ == "__main__":
    main()
