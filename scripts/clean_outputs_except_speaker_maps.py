#!/usr/bin/env python3
"""
One-off script to delete all files and subfolders from subfolders of /outputs,
except for speaker map JSON files.

Speaker map files follow the pattern: *_speaker_map.json
Keeps the transcript-level folders but deletes all subfolders like acts, contagion, etc.
"""

import os
import sys
import shutil
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"

def is_speaker_map_file(file_path: Path) -> bool:
    """Check if a file is a speaker map JSON file."""
    return file_path.name.endswith("_speaker_map.json")


def clean_outputs_directory():
    """Delete all files and subfolders in outputs subfolders except speaker map JSONs."""
    if not OUTPUTS_DIR.exists():
        print(f"Outputs directory does not exist: {OUTPUTS_DIR}")
        return
    
    deleted_files = 0
    deleted_dirs = 0
    kept_count = 0
    
    # Iterate through all subfolders in outputs (transcript folders)
    for transcript_folder in sorted(OUTPUTS_DIR.iterdir()):
        if not transcript_folder.is_dir():
            continue
        
        print(f"\nProcessing: {transcript_folder.name}")
        
        # Process all items in the transcript folder
        for item in sorted(transcript_folder.iterdir()):
            if item.is_file():
                # Keep speaker map files, delete everything else
                if is_speaker_map_file(item):
                    print(f"  Keeping: {item.relative_to(OUTPUTS_DIR)}")
                    kept_count += 1
                else:
                    try:
                        item.unlink()
                        print(f"  Deleted file: {item.relative_to(OUTPUTS_DIR)}")
                        deleted_files += 1
                    except Exception as e:
                        print(f"  Error deleting {item.relative_to(OUTPUTS_DIR)}: {e}")
            elif item.is_dir():
                # Delete entire subdirectory (acts, contagion, etc.)
                try:
                    shutil.rmtree(item)
                    print(f"  Deleted directory: {item.relative_to(OUTPUTS_DIR)}")
                    deleted_dirs += 1
                except Exception as e:
                    print(f"  Error deleting directory {item.relative_to(OUTPUTS_DIR)}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Files deleted: {deleted_files}")
    print(f"  Directories deleted: {deleted_dirs}")
    print(f"  Speaker map files kept: {kept_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    print("This script will delete all files and subfolders in outputs subfolders")
    print("except for speaker map JSON files (*_speaker_map.json)")
    print("Keeps transcript-level folders but deletes subfolders like acts, contagion, etc.")
    print(f"Outputs directory: {OUTPUTS_DIR}")
    
    # Check for --yes flag to skip confirmation
    skip_confirmation = '--yes' in sys.argv or '-y' in sys.argv
    
    if not skip_confirmation:
        response = input("\nDo you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Operation cancelled.")
            sys.exit(0)
    
    clean_outputs_directory()
