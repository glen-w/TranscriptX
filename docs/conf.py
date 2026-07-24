# Sphinx configuration for TranscriptX hosted docs (0.9.5 revive).
# Build: make docs  |  sphinx-build -b html docs docs/_build/html

from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

project = "TranscriptX"
author = "TranscriptX contributors"
copyright = f"{date.today().year}, {author}"
release = "0.9.5"
version = "0.9"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "archive/**",
    "**/archive/**",
    # Planning / programme sheets stay in-repo; not hosted nav by default.
    "dev/pre_release_roadmap_1_0.md",
    "dev/documentation_inventory_1_0.md",
    "dev/script_inventory_1_0.md",
    "dev/*_20*.md",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "replacements",
    "smartquotes",
    "strikethrough",
    "tasklist",
]
myst_heading_anchors = 3
# Many Markdown files use GitHub-style relative links; do not fail the build on
# every unresolved cross-page edge during the first revive.
suppress_warnings = ["myst.xref_missing", "misc.highlighting_failure"]

html_theme = "furo"
html_title = "TranscriptX"
html_static_path = ["_static"]

# Prefer package version when installed.
try:
    from importlib.metadata import version as pkg_version

    release = pkg_version("transcriptx")
    version = ".".join(release.split(".")[:2])
except Exception:
    pass
