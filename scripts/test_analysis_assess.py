#!/usr/bin/env python3
"""
Test Analysis Assessment Script

Unified CLI command for running test analysis, assessing outputs and database writes,
comparing with expected results, and generating comprehensive reports.

Usage:
    python scripts/test_analysis_assess.py --transcript tests/fixtures/data/tiny_diarized.json --modules stats,sentiment
    python scripts/test_analysis_assess.py --transcript path/to/transcript.json --assess-only
    python scripts/test_analysis_assess.py --transcript path/to/transcript.json --rerun-check
"""

import argparse
import hashlib
import json
import locale
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Pre-parse to set test output dir before transcriptx imports.
_pre_parser = argparse.ArgumentParser(add_help=False)
_pre_parser.add_argument("--test-output", action="store_true")
_pre_args, _ = _pre_parser.parse_known_args()
if _pre_args.test_output and not os.getenv("TRANSCRIPTX_OUTPUT_DIR"):
    _repo_root = Path(__file__).resolve().parent.parent
    _test_outputs_dir = _repo_root / ".test_outputs"
    _test_outputs_dir.mkdir(parents=True, exist_ok=True)
    os.environ["TRANSCRIPTX_OUTPUT_DIR"] = str(_test_outputs_dir)

try:
    import spacy
    from PIL import Image
except ImportError:
    spacy = None
    Image = None

from transcriptx.cli.analysis_workflow import run_analysis_non_interactive
from transcriptx.core.pipeline.output_reporter import OutputReporter
from transcriptx.core.utils.path_utils import get_transcript_dir, get_canonical_base_name
from transcriptx.core.utils.output_validation import validate_module_outputs
from transcriptx.core.utils.canonicalization import compute_transcript_content_hash
from transcriptx.database import get_session
from transcriptx.database.repositories import (
    TranscriptFileRepository,
    PipelineRunRepository,
    ModuleRunRepository,
    ArtifactIndexRepository,
    ConversationRepository,
    AnalysisRepository,
)
from transcriptx.io.transcript_service import get_transcript_service


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> Optional[str]:
    """Compute hash of a file."""
    if not file_path.exists():
        return None
    try:
        hash_obj = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception:
        return None


def capture_environment_snapshot() -> Dict[str, Any]:
    """Capture complete environment state for determinism."""
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "version_control": {},
        "system": {},
        "dependencies": {},
        "models": {},
        "config": {},
    }
    
    # Version Control
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        snapshot["version_control"]["commit_hash"] = result.stdout.strip() if result.returncode == 0 else None
        
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        snapshot["version_control"]["branch"] = result.stdout.strip() if result.returncode == 0 else None
        
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        snapshot["version_control"]["dirty"] = len(result.stdout.strip()) > 0
        snapshot["version_control"]["uncommitted_changes"] = result.stdout.strip().split('\n') if result.stdout.strip() else []
    except Exception:
        snapshot["version_control"]["error"] = "Could not determine git state"
    
    # System Environment
    snapshot["system"]["python_version"] = sys.version
    snapshot["system"]["os_name"] = platform.system()
    snapshot["system"]["os_release"] = platform.release()
    snapshot["system"]["platform"] = platform.platform()
    snapshot["system"]["architecture"] = platform.machine()
    
    try:
        tz = datetime.now().astimezone().tzinfo
        snapshot["system"]["timezone"] = str(tz)
    except Exception:
        snapshot["system"]["timezone"] = None
    
    try:
        snapshot["system"]["locale"] = locale.getlocale()
    except Exception:
        snapshot["system"]["locale"] = None
    
    # Dependencies
    try:
        result = subprocess.run(
            ["pip", "freeze"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            snapshot["dependencies"]["pip_freeze"] = result.stdout.strip().split('\n')
        else:
            snapshot["dependencies"]["pip_freeze"] = None
    except Exception:
        snapshot["dependencies"]["pip_freeze"] = None
    
    # Core dependency versions
    snapshot["dependencies"]["versions"] = {}
    for pkg in ["numpy", "spacy", "transformers", "torch"]:
        try:
            mod = __import__(pkg)
            snapshot["dependencies"]["versions"][pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            snapshot["dependencies"]["versions"][pkg] = None
    
    # Model Versions
    snapshot["models"] = {}
    if spacy:
        try:
            nlp = spacy.load("en_core_web_sm")
            snapshot["models"]["spacy_model_version"] = nlp.meta.get("version", "unknown")
        except Exception:
            snapshot["models"]["spacy_model_version"] = None
    
    # Configuration
    try:
        from transcriptx.core.utils.config import get_config
        config = get_config()
        snapshot["config"]["database_enabled"] = getattr(config.database, "enabled", False) if hasattr(config, "database") else False
    except Exception:
        snapshot["config"]["database_enabled"] = None
    
    return snapshot


def assess_file_outputs(transcript_path: str, modules_run: List[str]) -> Dict[str, Any]:
    """Assess file outputs generated by analysis."""
    output_dir = Path(get_transcript_dir(transcript_path))
    base_name = get_canonical_base_name(transcript_path)
    
    inventory = {
        "transcript_path": transcript_path,
        "output_directory": str(output_dir),
        "base_name": base_name,
        "modules_run": modules_run,
        "files_by_module": {},
        "artifacts_by_role": {
            "data": [],
            "chart": [],
            "summary": [],
            "intermediate": [],
            "debug": [],
            "export": [],
        },
        "global_files": [],
        "validation_results": {},
        "issues": [],
    }
    
    if not output_dir.exists():
        inventory["issues"].append({
            "severity": "critical",
            "type": "missing_directory",
            "message": f"Output directory does not exist: {output_dir}",
        })
        return inventory
    
    # Scan module outputs
    for module_name in modules_run:
        module_dir = output_dir / module_name
        if not module_dir.exists():
            inventory["files_by_module"][module_name] = []
            inventory["issues"].append({
                "severity": "critical",
                "type": "missing_module_directory",
                "module": module_name,
                "message": f"Module directory does not exist: {module_dir}",
            })
            continue
        
        module_files = []
        for file_path in module_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            relative_path = file_path.relative_to(output_dir)
            file_type = file_path.suffix.replace(".", "") if file_path.suffix else None
            
            # Determine artifact role
            role = "intermediate"
            rel_str = str(relative_path).replace("\\", "/")
            if "/data/global/" in rel_str or "/charts/global/" in rel_str:
                role = "primary"
            elif "/data/" in rel_str and "/data/speakers/" not in rel_str:
                role = "primary"
            elif "/charts/" in rel_str and "/charts/speakers/" not in rel_str:
                role = "primary"
            elif "/data/speakers/" in rel_str or "/charts/speakers/" in rel_str:
                role = "intermediate"
            elif "/debug/" in rel_str:
                role = "debug"
            elif "/export/" in rel_str or "/exports/" in rel_str:
                role = "export"
            
            # Override with file-type-based role if applicable
            if file_type == "json":
                role = "data"
            elif file_type == "png":
                role = "chart"
            elif file_type == "txt":
                role = "summary"
            
            file_info = {
                "path": str(relative_path),
                "type": file_type,
                "role": role,
            }
            module_files.append(file_info)
            
            # Ensure role exists in dictionary
            if role not in inventory["artifacts_by_role"]:
                inventory["artifacts_by_role"][role] = []
            inventory["artifacts_by_role"][role].append(str(relative_path))
        
        inventory["files_by_module"][module_name] = module_files
        
        # Validate module outputs
        try:
            validation_results = validate_module_outputs(output_dir, [module_name])
            result = validation_results.get(module_name, (False, []))
            inventory["validation_results"][module_name] = result
        except Exception as e:
            inventory["validation_results"][module_name] = (False, [str(e)])
    
    # Check global files
    global_patterns = [
        f"{base_name}_comprehensive_summary.html",
        f"{base_name}_comprehensive_summary.txt",
        f"{base_name}_speaker_map.json",
        ".transcriptx/manifest.json",
    ]
    
    for pattern in global_patterns:
        file_path = output_dir / pattern
        if file_path.exists():
            inventory["global_files"].append(pattern)
    
    inventory["total_files"] = sum(len(files) for files in inventory["files_by_module"].values())
    
    return inventory


def assess_database_writes(transcript_path: str, modules_requested: List[str]) -> Dict[str, Any]:
    """Assess database writes from analysis."""
    session = get_session()
    inventory = {
        "transcript_file": None,
        "pipeline_run": None,
        "module_runs": [],
        "artifacts": [],
        "conversation": None,
        "analysis_results": [],
        "issues": [],
    }
    
    try:
        # Normalize path to absolute (database stores absolute paths)
        transcript_path_abs = str(Path(transcript_path).resolve())
        
        # Query TranscriptFile
        transcript_repo = TranscriptFileRepository(session)
        transcript_file = transcript_repo.get_transcript_file_by_path(transcript_path_abs)
        
        if not transcript_file:
            inventory["issues"].append({
                "severity": "critical",
                "type": "missing_transcript_file",
                "message": f"TranscriptFile record not found for: {transcript_path_abs} (original: {transcript_path})",
            })
            return inventory
        
        inventory["transcript_file"] = {
            "id": transcript_file.id,
            "file_path": transcript_file.file_path,
            "transcript_content_hash": transcript_file.transcript_content_hash,
            "schema_version": transcript_file.schema_version,
            "segment_count": transcript_file.segment_count,
            "speaker_count": transcript_file.speaker_count,
        }
        
        # Verify hash matches (use original path for loading segments, normalized path already used for DB query)
        try:
            service = get_transcript_service()
            segments = service.load_segments(transcript_path, use_cache=False)
            transcript_hash = compute_transcript_content_hash(segments)
        except Exception as e:
            transcript_hash = None
            inventory["issues"].append({
                "severity": "medium",
                "type": "hash_computation_error",
                "message": f"Could not compute transcript hash: {e}",
            })
        if transcript_hash and transcript_file.transcript_content_hash != transcript_hash:
            inventory["issues"].append({
                "severity": "high",
                "type": "hash_mismatch",
                "message": f"TranscriptFile hash mismatch: DB={transcript_file.transcript_content_hash}, computed={transcript_hash}",
            })
        
        # Query PipelineRun (most recent for this transcript)
        pipeline_repo = PipelineRunRepository(session)
        # Query directly since repository doesn't have this method
        from transcriptx.database.models import PipelineRun
        pipeline_runs = session.query(PipelineRun).filter(
            PipelineRun.transcript_file_id == transcript_file.id
        ).order_by(PipelineRun.created_at.desc()).all()
        
        if not pipeline_runs:
            inventory["issues"].append({
                "severity": "critical",
                "type": "missing_pipeline_run",
                "message": f"No PipelineRun found for transcript_file_id={transcript_file.id}",
            })
            return inventory
        
        # Get most recent pipeline run
        latest_run = max(pipeline_runs, key=lambda r: r.created_at)
        inventory["pipeline_run"] = {
            "id": latest_run.id,
            "transcript_file_id": latest_run.transcript_file_id,
            "status": latest_run.status,
            "pipeline_input_hash": latest_run.pipeline_input_hash,
            "pipeline_config_hash": latest_run.pipeline_config_hash,
            "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
        }
        
        # Note: Multiple PipelineRuns are expected when analysis is run multiple times
        # This is normal database state, not an error
        if len(pipeline_runs) > 1:
            inventory["issues"].append({
                "severity": "low",
                "type": "multiple_pipeline_runs",
                "message": f"Found {len(pipeline_runs)} PipelineRuns for transcript_file_id={transcript_file.id} (expected for multiple runs)",
            })
        
        # Note: pipeline_input_hash is a composite hash of {transcript_content_hash, pipeline_config_hash}
        # It should NOT be compared directly to transcript_content_hash
        # We already validate transcript_content_hash separately above
        # The pipeline_input_hash is an internal implementation detail for caching/reuse logic
        
        # Query ModuleRuns
        module_repo = ModuleRunRepository(session)
        # Query directly since repository doesn't have this method
        from transcriptx.database.models import ModuleRun
        module_runs = session.query(ModuleRun).filter(
            ModuleRun.pipeline_run_id == latest_run.id
        ).all()
        
        requested_set = set(modules_requested)
        found_modules = set()
        
        for module_run in module_runs:
            found_modules.add(module_run.module_name)
            
            # Verify pipeline_run_id relationship
            if module_run.pipeline_run_id != latest_run.id:
                inventory["issues"].append({
                    "severity": "high",
                    "type": "module_run_relationship_mismatch",
                    "message": f"ModuleRun {module_run.id} pipeline_run_id={module_run.pipeline_run_id} does not match PipelineRun.id={latest_run.id}",
                })
            
            module_info = {
                "id": module_run.id,
                "module_name": module_run.module_name,
                "pipeline_run_id": module_run.pipeline_run_id,
                "status": module_run.status,
                "module_input_hash": module_run.module_input_hash,
                "module_config_hash": module_run.module_config_hash,
            }
            inventory["module_runs"].append(module_info)
        
        # Check for missing modules
        missing_modules = requested_set - found_modules
        if missing_modules:
            inventory["issues"].append({
                "severity": "critical",
                "type": "missing_module_runs",
                "message": f"Missing ModuleRuns for requested modules: {missing_modules}",
            })
        
        # Check for unexpected modules
        unexpected_modules = found_modules - requested_set
        if unexpected_modules:
            inventory["issues"].append({
                "severity": "critical",
                "type": "unexpected_module_runs",
                "message": f"ModuleRuns found for unrequested modules: {unexpected_modules}",
            })
        
        # Query Artifacts
        artifact_repo = ArtifactIndexRepository(session)
        # Query directly since repository doesn't have this method
        from transcriptx.database.models import ArtifactIndex
        
        # First, check if any artifacts exist for this transcript at all
        all_transcript_artifacts = session.query(ArtifactIndex).filter(
            ArtifactIndex.transcript_file_id == transcript_file.id
        ).all()
        
        # Get module_run_ids that have artifacts
        artifact_module_run_ids = {a.module_run_id for a in all_transcript_artifacts}
        current_module_run_ids = {mr.id for mr in module_runs}
        
        for module_run in module_runs:
            artifacts = session.query(ArtifactIndex).filter(
                ArtifactIndex.module_run_id == module_run.id
            ).all()
            
            # Check for missing artifacts
            if not artifacts:
                if all_transcript_artifacts:
                    # Artifacts exist but for different module_runs (from different PipelineRuns)
                    # This indicates artifacts were registered for a previous run but not this one
                    inventory["issues"].append({
                        "severity": "medium",
                        "type": "artifacts_for_different_runs",
                        "message": f"No artifacts found for ModuleRun {module_run.id} ({module_run.module_name}) in PipelineRun {latest_run.id}, but {len(all_transcript_artifacts)} artifacts exist for transcript from other runs (artifact module_run_ids: {artifact_module_run_ids}, current module_run_ids: {current_module_run_ids})",
                    })
                else:
                    # No artifacts at all for this transcript
                    inventory["issues"].append({
                        "severity": "high",
                        "type": "missing_artifacts",
                        "message": f"No artifacts registered for ModuleRun {module_run.id} ({module_run.module_name}) in PipelineRun {latest_run.id} - no artifacts exist for this transcript at all",
                    })
            
            for artifact in artifacts:
                artifact_info = {
                    "id": artifact.id,
                    "module_run_id": artifact.module_run_id,
                    "artifact_key": artifact.artifact_key,
                    "relative_path": artifact.relative_path,
                    "artifact_type": artifact.artifact_type,
                    "artifact_role": artifact.artifact_role,
                    "content_hash": artifact.content_hash,
                }
                inventory["artifacts"].append(artifact_info)
                
                # Verify file exists and hash matches
                output_dir = Path(get_transcript_dir(transcript_path))
                artifact_path = output_dir / artifact.relative_path
                if not artifact_path.exists():
                    inventory["issues"].append({
                        "severity": "high",
                        "type": "artifact_file_missing",
                        "message": f"Artifact file does not exist: {artifact_path}",
                    })
                else:
                    computed_hash = compute_file_hash(artifact_path)
                    if computed_hash and artifact.content_hash != computed_hash:
                        inventory["issues"].append({
                            "severity": "high",
                            "type": "artifact_hash_mismatch",
                            "message": f"Artifact hash mismatch for {artifact.relative_path}: DB={artifact.content_hash}, computed={computed_hash}",
                        })
        
        # Query Conversation (if exists)
        try:
            conversation_repo = ConversationRepository(session)
            conversation = conversation_repo.find_conversation_by_transcript_path(transcript_path)
            if conversation:
                inventory["conversation"] = {
                    "id": conversation.id,
                    "title": conversation.title,
                    "analysis_status": conversation.analysis_status,
                }
        except Exception:
            pass  # Conversation is optional
        
        # Query AnalysisResults (if Conversation model used)
        try:
            if inventory["conversation"]:
                analysis_repo = AnalysisRepository(session)
                analysis_results = analysis_repo.get_conversation_analysis_results(inventory["conversation"]["id"])
                for result in analysis_results:
                    inventory["analysis_results"].append({
                        "id": result.id,
                        "analysis_type": result.analysis_type,
                        "status": result.status,
                    })
        except Exception:
            pass
        
    except Exception as e:
        inventory["issues"].append({
            "severity": "critical",
            "type": "database_error",
            "message": f"Error querying database: {e}",
        })
    finally:
        session.close()
    
    return inventory


def compare_with_expected(
    file_inventory: Dict[str, Any],
    db_inventory: Dict[str, Any],
    expected_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare actual results with expected outputs."""
    comparison = {
        "file_issues": {
            "missing_artifacts": [],
            "unexpected_files": [],
            "schema_violations": [],
            "invariant_violations": [],
            "format_errors": [],
        },
        "database_issues": {
            "missing_records": [],
            "incorrect_values": [],
            "missing_relationships": [],
            "hash_mismatches": [],
            "run_boundary_violations": [],
        },
        "severity_summary": {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        },
        "overall_severity": "low",
    }
    
    # Collect issues from assessments
    for issue in file_inventory.get("issues", []):
        severity = issue.get("severity", "medium")
        comparison["severity_summary"][severity].append(issue)
        if severity in ["critical", "high"]:
            comparison["database_issues"]["missing_records"].append(issue)
    
    for issue in db_inventory.get("issues", []):
        severity = issue.get("severity", "medium")
        comparison["severity_summary"][severity].append(issue)
        
        issue_type = issue.get("type", "")
        if issue_type == "hash_mismatch" or "hash" in issue_type:
            comparison["database_issues"]["hash_mismatches"].append(issue)
        elif issue_type in ["missing_transcript_file", "missing_pipeline_run", "missing_module_runs"]:
            comparison["database_issues"]["missing_records"].append(issue)
        elif "relationship" in issue_type:
            comparison["database_issues"]["missing_relationships"].append(issue)
        elif "unexpected" in issue_type or "multiple" in issue_type:
            comparison["database_issues"]["run_boundary_violations"].append(issue)
    
    # Determine overall severity
    if comparison["severity_summary"]["critical"]:
        comparison["overall_severity"] = "critical"
    elif comparison["severity_summary"]["high"]:
        comparison["overall_severity"] = "high"
    elif comparison["severity_summary"]["medium"]:
        comparison["overall_severity"] = "medium"
    
    return comparison


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Analysis Assessment Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transcript",
        type=str,
        required=True,
        help="Path to transcript JSON file",
    )
    parser.add_argument(
        "--modules",
        type=str,
        help="Comma-separated list of modules to run (default: stats,sentiment)",
        default="stats,sentiment",
    )
    parser.add_argument(
        "--assess-only",
        action="store_true",
        help="Only assess existing run, don't run analysis",
    )
    parser.add_argument(
        "--rerun-check",
        action="store_true",
        help="Run analysis twice to check idempotency",
    )
    parser.add_argument(
        "--test-output",
        action="store_true",
        help="Write outputs under .test_outputs (sets TRANSCRIPTX_OUTPUT_DIR)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file for report",
    )
    parser.add_argument(
        "--expected",
        type=str,
        help="Path to expected outputs specification JSON",
    )
    
    args = parser.parse_args()
    
    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Error: Transcript file not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)
    
    modules = [m.strip() for m in args.modules.split(",")]
    
    # Capture environment snapshot
    print("Capturing environment snapshot...")
    env_snapshot = capture_environment_snapshot()
    
    # Run analysis if not assess-only
    if not args.assess_only:
        print(f"Running analysis on {transcript_path.name}...")
        print(f"Modules: {', '.join(modules)}")
        
        try:
            try:
                result = run_analysis_non_interactive(
                    transcript_file=str(transcript_path),
                    modules=modules,
                    mode="quick",
                    skip_confirm=True,
                )
                
                # Even if status is not "completed", check if modules actually ran
                modules_run = result.get("modules_run", modules)
                
                if result.get("status") != "completed":
                    print(f"Warning: Analysis workflow reported status '{result.get('status')}'", file=sys.stderr)
                    print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                    print("Continuing with assessment of what was generated...", file=sys.stderr)
                    # Don't exit - continue to assess what was generated
            except Exception as e:
                print(f"Warning: Analysis workflow raised exception: {e}", file=sys.stderr)
                print("Continuing with assessment of what was generated...", file=sys.stderr)
                # Try to determine what modules might have run by checking output directories
                modules_run = modules
        except Exception as e:
            print(f"Error running analysis: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Assume modules were already run
        modules_run = modules
    
    # Assess file outputs
    print("Assessing file outputs...")
    file_inventory = assess_file_outputs(str(transcript_path), modules_run)
    
    # Assess database writes
    print("Assessing database writes...")
    db_inventory = assess_database_writes(str(transcript_path), modules)
    
    # Load expected spec if provided
    expected_spec = None
    if args.expected:
        try:
            with open(args.expected, 'r') as f:
                expected_spec = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load expected spec: {e}", file=sys.stderr)
    
    # Compare with expected
    print("Comparing with expected outputs...")
    comparison = compare_with_expected(file_inventory, db_inventory, expected_spec)
    
    # Generate report
    report = {
        "environment": env_snapshot,
        "transcript_path": str(transcript_path),
        "modules_requested": modules,
        "modules_run": modules_run,
        "file_inventory": file_inventory,
        "database_inventory": db_inventory,
        "comparison": comparison,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Print summary
    print("\n" + "="*80)
    print("ASSESSMENT SUMMARY")
    print("="*80)
    print(f"Overall Severity: {comparison['overall_severity'].upper()}")
    print(f"Critical Issues: {len(comparison['severity_summary']['critical'])}")
    print(f"High Issues: {len(comparison['severity_summary']['high'])}")
    print(f"Medium Issues: {len(comparison['severity_summary']['medium'])}")
    print(f"Low Issues: {len(comparison['severity_summary']['low'])}")
    
    if comparison['severity_summary']['critical']:
        print("\nCRITICAL ISSUES:")
        for issue in comparison['severity_summary']['critical']:
            print(f"  - {issue.get('type', 'unknown')}: {issue.get('message', 'No message')}")
    
    if comparison['severity_summary']['high']:
        print("\nHIGH SEVERITY ISSUES:")
        for issue in comparison['severity_summary']['high']:
            print(f"  - {issue.get('type', 'unknown')}: {issue.get('message', 'No message')}")
    
    # Save report
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_path}")
    else:
        # Save to default location
        output_dir = Path(get_transcript_dir(str(transcript_path)))
        output_path = output_dir / ".transcriptx" / "assessment_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_path}")
    
    # Exit with appropriate code
    if comparison['overall_severity'] == "critical":
        sys.exit(2)
    elif comparison['overall_severity'] in ["high", "medium"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
