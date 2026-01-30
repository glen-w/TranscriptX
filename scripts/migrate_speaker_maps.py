#!/usr/bin/env python3
"""
Migration script to update existing speaker maps and transcripts.

This script:
1. Finds all existing speaker_map.json files
2. Updates corresponding transcript JSON files with speaker names
3. Creates/updates speakers in database with parsed names (first_name, surname)
4. Handles duplicate names intelligently
5. Updates database segments if they exist

Usage:
    python scripts/migrate_speaker_maps.py [--dry-run] [--verbose]
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.path_utils import get_canonical_base_name, get_speaker_map_path
from transcriptx.core.utils.speaker import parse_speaker_name, format_speaker_display_name
from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.repositories import SpeakerRepository, TranscriptFileRepository
from transcriptx.io.speaker_mapping import update_transcript_json_with_speaker_names

logger = get_logger()


def find_all_speaker_maps() -> List[Tuple[str, str]]:
    """
    Find all speaker map files and their corresponding transcripts.
    
    Returns:
        List of (speaker_map_path, transcript_path) tuples
    """
    speaker_maps = []
    outputs_dir = Path(OUTPUTS_DIR)
    transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    
    # Find all speaker_map.json files in outputs directory
    if outputs_dir.exists():
        for speaker_map_file in outputs_dir.rglob("*_speaker_map.json"):
            # Extract base name from speaker map path
            base_name = speaker_map_file.stem.replace("_speaker_map", "")
            
            # Try to find corresponding transcript
            transcript_candidates = [
                transcripts_dir / f"{base_name}.json",
                transcripts_dir / f"{base_name}_transcript_diarised.json",
                outputs_dir / base_name / f"{base_name}.json",
            ]
            
            transcript_path = None
            for candidate in transcript_candidates:
                if candidate.exists():
                    transcript_path = str(candidate.resolve())
                    break
            
            if transcript_path:
                speaker_maps.append((str(speaker_map_file.resolve()), transcript_path))
            else:
                logger.warning(f"Could not find transcript for speaker map: {speaker_map_file}")
    
    return speaker_maps


def migrate_speaker_map(
    speaker_map_path: str,
    transcript_path: str,
    dry_run: bool = False,
    verbose: bool = False
) -> Dict[str, any]:
    """
    Migrate a single speaker map.
    
    Args:
        speaker_map_path: Path to speaker map JSON file
        transcript_path: Path to transcript JSON file
        dry_run: If True, don't make changes
        verbose: If True, print detailed output
        
    Returns:
        Dictionary with migration results
    """
    results = {
        "speaker_map_path": speaker_map_path,
        "transcript_path": transcript_path,
        "speakers_created": 0,
        "speakers_updated": 0,
        "speakers_linked": 0,
        "transcript_updated": False,
        "errors": []
    }
    
    try:
        # Load speaker map
        with open(speaker_map_path, 'r') as f:
            speaker_map = json.load(f)
        
        # Normalize speaker IDs (handle "1" -> "SPEAKER_01")
        normalized_map = {}
        for k, v in speaker_map.items():
            if str(k).isdigit():
                normalized_id = f"SPEAKER_{int(k):02d}"
            else:
                normalized_id = k
            normalized_map[normalized_id] = v
        
        if verbose:
            print(f"\n📋 Processing: {Path(transcript_path).name}")
            print(f"   Found {len(normalized_map)} speakers in map")
        
        # Get database session
        session = get_session()
        speaker_repo = SpeakerRepository(session)
        speaker_id_to_db_id = {}
        
        # Process each speaker
        for speaker_id, speaker_name in normalized_map.items():
            try:
                # Parse name
                first_name, surname = parse_speaker_name(speaker_name)
                
                # Check for duplicates
                existing_speakers = speaker_repo.find_speakers_by_name(
                    first_name, surname, active_only=True
                )
                
                if existing_speakers:
                    # Use first existing speaker (in migration, we link to existing)
                    selected_speaker = existing_speakers[0]
                    speaker_id_to_db_id[speaker_id] = selected_speaker.id
                    results["speakers_linked"] += 1
                    
                    if verbose:
                        print(f"   🔗 Linked '{speaker_name}' to existing speaker (ID: {selected_speaker.id})")
                else:
                    # Create new speaker
                    if not dry_run:
                        display_name = format_speaker_display_name(
                            first_name=first_name,
                            surname=surname,
                            name=speaker_name
                        )
                        
                        speaker = speaker_repo.create_speaker(
                            name=speaker_name,
                            display_name=display_name,
                            first_name=first_name,
                            surname=surname,
                            personal_note=None  # Can be added manually later
                        )
                        speaker_id_to_db_id[speaker_id] = speaker.id
                        results["speakers_created"] += 1
                        
                        if verbose:
                            print(f"   ✅ Created speaker: {speaker_name} (ID: {speaker.id})")
                    else:
                        results["speakers_created"] += 1
                        if verbose:
                            print(f"   [DRY RUN] Would create speaker: {speaker_name}")
            
            except Exception as e:
                error_msg = f"Failed to process speaker '{speaker_name}': {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        # Update transcript JSON
        if not dry_run:
            try:
                update_transcript_json_with_speaker_names(
                    transcript_path,
                    normalized_map,
                    speaker_id_to_db_id
                )
                results["transcript_updated"] = True
                
                if verbose:
                    print(f"   ✅ Updated transcript JSON with speaker names")
            except Exception as e:
                error_msg = f"Failed to update transcript JSON: {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        else:
            results["transcript_updated"] = True
            if verbose:
                print(f"   [DRY RUN] Would update transcript JSON")
        
        if not dry_run:
            session.commit()
        
        session.close()
        
    except Exception as e:
        error_msg = f"Failed to migrate speaker map: {e}"
        results["errors"].append(error_msg)
        logger.error(error_msg)
    
    return results


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate existing speaker maps to new format")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would be done")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--transcript", help="Migrate specific transcript (by base name)")
    
    args = parser.parse_args()
    
    print("🔍 Finding speaker maps...")
    speaker_maps = find_all_speaker_maps()
    
    if not speaker_maps:
        print("❌ No speaker maps found")
        return
    
    print(f"✅ Found {len(speaker_maps)} speaker map(s)")
    
    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")
    
    # Filter by transcript if specified
    if args.transcript:
        speaker_maps = [
            (sm_path, t_path) for sm_path, t_path in speaker_maps
            if args.transcript in Path(t_path).stem
        ]
        if not speaker_maps:
            print(f"❌ No speaker maps found for transcript: {args.transcript}")
            return
    
    # Process each speaker map
    all_results = []
    total_created = 0
    total_linked = 0
    total_updated = 0
    
    for speaker_map_path, transcript_path in speaker_maps:
        results = migrate_speaker_map(
            speaker_map_path,
            transcript_path,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        all_results.append(results)
        
        total_created += results["speakers_created"]
        total_linked += results["speakers_linked"]
        total_updated += 1 if results["transcript_updated"] else 0
    
    # Summary
    print("\n" + "="*60)
    print("📊 Migration Summary")
    print("="*60)
    print(f"Processed: {len(all_results)} transcript(s)")
    print(f"Speakers created: {total_created}")
    print(f"Speakers linked: {total_linked}")
    print(f"Transcripts updated: {total_updated}")
    
    # Show errors if any
    all_errors = [e for r in all_results for e in r["errors"]]
    if all_errors:
        print(f"\n⚠️  Errors: {len(all_errors)}")
        for error in all_errors:
            print(f"   - {error}")
    
    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()
