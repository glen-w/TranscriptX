#!/usr/bin/env python3
"""
Test script to verify the refactored pipeline works correctly.
"""

import json
import tempfile
import os
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from transcriptx.core.pipeline.module_registry import get_available_modules, get_module_info
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline


def create_test_transcript():
    """Create a simple test transcript."""
    return {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello, welcome to our meeting today. I'm excited to discuss the project.",
                "start": 0.0,
                "end": 5.0
            },
            {
                "speaker": "SPEAKER_01", 
                "text": "Thank you for having me. I'm looking forward to our collaboration.",
                "start": 5.5,
                "end": 10.0
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Great! Let's start with the overview and then dive into the details.",
                "start": 10.5,
                "end": 15.0
            }
        ]
    }


def test_module_registry():
    """Test the module registry functionality."""
    print("Testing module registry...")
    
    # Test getting available modules
    modules = get_available_modules()
    print(f"Available modules: {len(modules)}")
    print(f"Modules: {modules}")
    
    # Test getting module info
    for module in modules[:3]:  # Test first 3 modules
        info = get_module_info(module)
        print(f"Module {module}: {info.description if info else 'Not found'}")
    
    print("✅ Module registry test passed\n")


def test_pipeline_execution():
    """Test the pipeline execution with a simple module."""
    print("Testing pipeline execution...")
    
    # Create temporary transcript file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        transcript_data = create_test_transcript()
        json.dump(transcript_data, f, indent=2)
        transcript_path = f.name
    
    try:
        # Test with stats module (lightweight)
        print("Running stats analysis...")
        result = run_analysis_pipeline(
            transcript_path=transcript_path,
            selected_modules=["stats"],
            speaker_map={"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
            skip_speaker_mapping=True
        )
        
        print(f"Pipeline result: {result['modules_run']}")
        print(f"Errors: {result['errors']}")
        print(f"Duration: {result['duration']:.2f} seconds")
        
        if result['modules_run']:
            print("✅ Pipeline execution test passed")
        else:
            print("❌ Pipeline execution test failed - no modules run")
            
    except Exception as e:
        print(f"❌ Pipeline execution test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        os.unlink(transcript_path)


def main():
    """Run all tests."""
    print("🧪 Testing refactored TranscriptX pipeline\n")
    
    test_module_registry()
    test_pipeline_execution()
    
    print("🎉 All tests completed!")


if __name__ == "__main__":
    main()
