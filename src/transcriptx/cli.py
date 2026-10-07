"""TranscriptX console entry: host CLI subcommands or Streamlit web UI."""

from __future__ import annotations

import sys
from typing import Sequence

_CLI_COMMANDS: dict[str, str] = {
    "import": "transcriptx.import_transcript",
    "admit-originals": "transcriptx.admit_originals",
    "analyze": "transcriptx.analyze",
    "analyze-backlog": "transcriptx.analyze_backlog",
    "cleanup-runs": "transcriptx.cleanup_runs",
    "rename": "transcriptx.rename_managed",
    "backup": "transcriptx.backup",
    "warm-suggestions": "transcriptx.warm_suggestions",
    "identify-speakers": "transcriptx.identify_speakers",
}


def _print_cli_help() -> None:
    print(
        "Usage: transcriptx [COMMAND] [ARGS...]\n"
        "\n"
        "Commands (host automation; no Streamlit):\n"
        "  import             Managed-import transcript file(s) into the library\n"
        "  admit-originals    Admit files already under originals/\n"
        "  analyze            Run analysis on one managed transcript\n"
        "  analyze-backlog    Analyze ready transcripts with no analysis yet\n"
        "  cleanup-runs       Bulk-delete old (or all) analysis run directories\n"
        "  rename             Rename a managed transcript (+ linked audio)\n"
        "  backup             Workspace ZIP create / verify / restore\n"
        "  warm-suggestions   Warm assistive LLM rename / speaker-name caches\n"
        "  identify-speakers  Auto-identify speakers (voice + text fusion)\n"
        "\n"
        "Interactive workspaces (Corrections, Speaker ID review, Charts/Ask)\n"
        "stay in the GUI. With no command, launches the Streamlit web UI.\n"
        "Examples:\n"
        "  transcriptx\n"
        "  transcriptx import path/to/raw.json\n"
        "  transcriptx analyze --path library/foo.json --preset balanced\n"
        "  transcriptx analyze-backlog --preset thorough --dry-run\n"
        "  transcriptx cleanup-runs --mode delete-old --keep-human-readable "
        "--keep-llm-summaries --dry-run\n"
        "  transcriptx backup create\n"
        "  transcriptx warm-suggestions --all\n"
        "  transcriptx identify-speakers --all-unnamed --dry-run\n"
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
