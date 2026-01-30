# Archived Scripts

This directory contains scripts that have been archived because they are:
- Duplicates of existing functionality
- Reference non-existent files or configurations
- One-off utilities that are no longer actively used
- Superseded by better implementations

## Archived Scripts

### `run_transcriptx.sh`
**Reason**: Duplicates functionality of `transcriptx.sh` (main launcher)  
**Status**: Superseded by `transcriptx.sh`  
**Date Archived**: 2024-12-19

### `docker-test.sh`
**Reason**: References docker-compose test profile that doesn't exist in current setup  
**Status**: No longer functional with current Docker configuration  
**Date Archived**: 2024-12-19  
**Note**: Current Docker setup only includes WhisperX service via `docker-compose.whisperx.yml`

### `test-docker-setup.sh`
**Reason**: References scripts and docker-compose files that no longer exist  
**Status**: No longer functional with current Docker configuration  
**Date Archived**: 2024-12-19  
**Note**: Tests referenced scripts like `docker-dev.sh`, `docker-prod.sh`, `docker-web.sh` which have been removed

### `migrate_diarised_transcripts.py`
**Reason**: One-off migration script to reorganize file structure  
**Status**: Migration completed - no longer needed  
**Date Archived**: 2025-01-09  
**Note**: Moved diarised transcript JSONs from `data/outputs/{session}/transcripts/` to `data/transcripts/`

### `migrate_mp3_files.py`
**Reason**: One-off migration script to reorganize file structure  
**Status**: Migration completed - no longer needed  
**Date Archived**: 2025-01-09  
**Note**: Moved MP3 files from `data/outputs/recordings/` to `data/recordings/`

### `test_pipeline_refactor.py`
**Reason**: One-off test script for pipeline refactoring verification  
**Status**: Testing completed - no longer needed  
**Date Archived**: 2025-01-09  
**Note**: Used to verify refactored pipeline functionality during development

### `check_spacy_models.py`
**Reason**: spaCy model verification utility  
**Status**: Still functional but moved to archived for organization  
**Date Archived**: 2025-01-09  
**Note**: Referenced in `transcriptx.sh` from archived location. Can be run manually if needed.

### `fix_installation.sh`
**Reason**: One-off installation fix script  
**Status**: Fix completed - no longer needed  
**Date Archived**: 2025-01-09  
**Note**: Fixed deprecation warning by using modern Python packaging (PEP 517)

### `transcriptx_interactive.py`
**Reason**: Duplicate entry point - functionality already in `transcriptx.sh`  
**Status**: Superseded by `transcriptx.sh`  
**Date Archived**: 2025-01-09  
**Note**: `transcriptx.sh` already handles interactive CLI launch via `python -m transcriptx.cli.main`

## Current Active Scripts

The following scripts remain in the main `scripts/` directory and are actively used:

- `transcriptx.sh` - Main launcher (replaces `run_transcriptx.sh`)
- `scripts/setup_env.sh` - Environment setup
- `scripts/docker-setup.sh` - Docker setup
- `scripts/whisperx-compose.sh` - WhisperX Docker Compose management
- `scripts/manage_dependencies.sh` - Dependency management
- `scripts/build_docs.sh` - Documentation build
- `scripts/validate_dependencies.py` - Dependency validation
- `scripts/cleanup.sh` - Codebase cleanup utility
- `scripts/docker-clean.sh` - Docker cleanup utility
- `scripts/docker-data-setup.sh` - Docker data directory setup

## Restoration

If you need to restore any of these scripts:
1. Check if the functionality is available in current scripts
2. Verify that referenced files/configurations exist
3. Test the script before using in production
4. Consider updating to match current project structure
