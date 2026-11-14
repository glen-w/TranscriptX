"""TranscriptX console entry: host CLI subcommands or Streamlit web UI."""

from __future__ import annotations

import sys
from typing import Sequence

# Single source for dispatch and ``--help``: (command, module, summary).
_CLI_COMMAND_TABLE: tuple[tuple[str, str, str], ...] = (
    (
        "import",
        "transcriptx.import_transcript",
        "Managed-import transcript file(s) into the library",
    ),
    (
        "admit-originals",
        "transcriptx.admit_originals",
        "Admit files already under originals/",
    ),
    ("analyze", "transcriptx.analyze", "Run analysis on one managed transcript"),
    (
        "analyze-backlog",
        "transcriptx.analyze_backlog",
        "Analyze ready transcripts with no analysis yet",
    ),
    (
        "analyze-modules",
        "transcriptx.analyze_modules",
        "Catch up selected modules across the library",
    ),
    (
        "cleanup-runs",
        "transcriptx.cleanup_runs",
        "Bulk-delete old (or all) analysis run directories",
    ),
    (
        "library-paths",
        "transcriptx.library_paths",
        "Print managed transcript paths (newest first)",
    ),
    (
        "rename",
        "transcriptx.rename_managed",
        "Rename a managed transcript (+ linked audio)",
    ),
    ("backup", "transcriptx.backup", "Workspace ZIP create / verify / restore"),
    (
        "warm-suggestions",
        "transcriptx.warm_suggestions",
        "Warm assistive LLM rename / speaker-name caches",
    ),
    (
        "identify-speakers",
        "transcriptx.identify_speakers",
        "Auto-identify speakers (voice + text fusion)",
    ),
)

_CLI_COMMANDS: dict[str, str] = {
    command: module for command, module, _summary in _CLI_COMMAND_TABLE
}


def _print_cli_help() -> None:
    commands = "".join(
        f"  {command:<18} {summary}\n"
        for command, _module, summary in _CLI_COMMAND_TABLE
    )
    print(
        "Usage: transcriptx [COMMAND] [ARGS...]\n"
        "\n"
        "Commands (host automation; no Streamlit):\n"
        f"{commands}"
        "\n"
        "Interactive workspaces (Corrections, Speaker ID review, Charts/Ask)\n"
        "stay in the GUI. With no command, launches the Streamlit web UI.\n"
        "Examples:\n"
        "  transcriptx\n"
        "  transcriptx import path/to/raw.json\n"
        "  transcriptx analyze --path library/foo.json --preset balanced\n"
        "  transcriptx analyze-backlog --preset thorough --dry-run\n"
        "  transcriptx analyze-modules --modules transcript_output,llm_summary "
        "--dry-run\n"
        "  transcriptx cleanup-runs --mode delete-old --keep-human-readable "
        "--keep-llm-summaries --dry-run\n"
        "  transcriptx backup create\n"
        "  transcriptx warm-suggestions --all\n"
        "  transcriptx identify-speakers --all-unnamed --dry-run\n"
        "  transcriptx library-paths --recent 3 --missing-modules transcript_output,llm_summary\n"
    )


def _dispatch_cli(argv: Sequence[str]) -> int | None:
    """Run a host subcommand when argv[0] is a known command name."""
    if not argv:
        return None
    token = argv[0].replace("_", "-")
    module_name = _CLI_COMMANDS.get(token)
    if module_name is None:
        return None
    import importlib

    mod = importlib.import_module(module_name)
    main = getattr(mod, "main", None)
    if main is None:
        print(f"ERROR: {module_name} has no main()", file=sys.stderr)
        return 2
    return int(main(list(argv[1:])))


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help", "help"):
        if len(argv) == 1:
            _print_cli_help()
            sys.exit(0)
    exit_code = _dispatch_cli(argv)
    if exit_code is not None:
        sys.exit(exit_code)
    from transcriptx.web.__main__ import main as web_main

    web_main()


if __name__ == "__main__":
    main()
