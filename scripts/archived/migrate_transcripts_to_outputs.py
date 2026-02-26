import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "transcripts" / "raw"
READABLE_DIR = PROJECT_ROOT / "data" / "transcripts" / "readable"
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"


def move_with_rules(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    final_dst = dst
    if dst.exists() and not overwrite:
        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while True:
            candidate = dst.with_name(f"{stem}__{i}{suffix}")
            if not candidate.exists():
                final_dst = candidate
                break
            i += 1
    if dry_run:
        print(f"DRY-RUN: {src} -> {final_dst}")
        return
    shutil.move(str(src), str(final_dst))
    print(f"Moved: {src} -> {final_dst}")


def session_name_from_path(p: Path) -> str:
    # session name equals file stem per current dataset, e.g., 251017_CSE
    return p.stem


def migrate_raw(json_file: Path, overwrite: bool, dry_run: bool) -> None:
    session = session_name_from_path(json_file)
    dst = OUTPUTS_DIR / session / "transcripts" / f"{session}_transcript_diarised.json"
    move_with_rules(json_file, dst, overwrite, dry_run)


def migrate_readable_txt(txt_file: Path, overwrite: bool, dry_run: bool) -> None:
    session = txt_file.stem.split("-")[0]
    dst = OUTPUTS_DIR / session / "transcripts" / f"{session}_transcript_readable.txt"
    move_with_rules(txt_file, dst, overwrite, dry_run)


def migrate_readable_csv(csv_file: Path, overwrite: bool, dry_run: bool) -> None:
    session = csv_file.stem.split("-")[0]
    dst = OUTPUTS_DIR / session / "transcripts" / f"{session}_transcript_readable.csv"
    move_with_rules(csv_file, dst, overwrite, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate transcripts to outputs/<session>/transcripts"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing destination files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions without moving files"
    )
    args = parser.parse_args()

    # Raw JSON transcripts
    if RAW_DIR.exists():
        for p in sorted(RAW_DIR.glob("*.json")):
            migrate_raw(p, overwrite=args.overwrite, dry_run=args.dry_run)

        # Also handle nested session folders that might contain a single json
        for session_dir in sorted(RAW_DIR.glob("*/")):
            for p in session_dir.glob("*.json"):
                migrate_raw(p, overwrite=args.overwrite, dry_run=args.dry_run)

    # Readable TXT/CSV
    if READABLE_DIR.exists():
        for p in sorted(READABLE_DIR.glob("*.txt")):
            migrate_readable_txt(p, overwrite=args.overwrite, dry_run=args.dry_run)
        for p in sorted(READABLE_DIR.glob("*.csv")):
            migrate_readable_csv(p, overwrite=args.overwrite, dry_run=args.dry_run)

    # Also migrate any readable files found under outputs legacy transcript_output summaries
    # by scanning outputs for files named "*-transcript.txt/csv" and moving them into transcripts/
    for session_dir in sorted(OUTPUTS_DIR.glob("*/")):
        for p in session_dir.glob("*-transcript.txt"):
            migrate_readable_txt(p, overwrite=args.overwrite, dry_run=args.dry_run)
        for p in session_dir.glob("*-transcript.csv"):
            migrate_readable_csv(p, overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
