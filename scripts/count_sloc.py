#!/usr/bin/env python3
"""Compare SLOC across tokei, scc, cloc, and radon.

Stdlib only. Path-agnostic: point at any repo with --root (default: cwd).

Prefers git-tracked files. Extra path filters drop vendored/generated trees
even when they are tracked. Prints a markdown comparison table and optional JSON.

Install counters (macOS):  python3 scripts/count_sloc.py --install
Measure:                    python3 scripts/count_sloc.py --root .
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "htmlcov",
    "site-packages",
}
SKIP_DIR_PREFIXES_TRACKED = {"archive", "artifacts"}
SKIP_SUFFIXES = {
    ".png",
    ".gif",
    ".jpg",
    ".jpeg",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".zip",
    ".gz",
    ".pyc",
    ".so",
    ".dylib",
    ".bin",
}
GENERATED_DIR_NAMES = {"build"}
NON_CODE_LANGS = {
    "markdown",
    "mdx",
    "json",
    "json5",
    "jsonc",
    "yaml",
    "yml",
    "toml",
    "xml",
    "text",
    "plain text",
    "svg",
    "license",
    "gitignore",
    "autohotkey",  # not expected; keep noise langs out of headlines
    "restructuredtext",
    "rst",
}
TEST_JS_SUFFIXES = (".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js")
BREW_TOOLS = ("tokei", "scc", "cloc")
ROLE_ORDER = ("product", "tests", "scripts", "config", "docs", "generated", "other")
CODE_TOOLS = ("tokei", "scc", "cloc")


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def run_cmd(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def install_tools() -> None:
    missing_brew = [t for t in BREW_TOOLS if not which(t)]
    brew = which("brew")
    if missing_brew:
        if not brew:
            eprint(f"warning: missing {', '.join(missing_brew)} and Homebrew is not on PATH")
        else:
            eprint(f"installing via Homebrew: {' '.join(missing_brew)}")
            proc = run_cmd([brew, "install", *missing_brew], timeout=600)
            if proc.returncode != 0:
                eprint(proc.stderr.strip() or proc.stdout.strip() or "brew install failed")
    if not which("radon"):
        eprint(f"installing radon via {sys.executable} -m pip")
        proc = run_cmd(
            [sys.executable, "-m", "pip", "install", "--user", "radon"],
            timeout=180,
        )
        if proc.returncode != 0:
            eprint(proc.stderr.strip() or proc.stdout.strip() or "pip install radon failed")


def git_ls_files(root: Path) -> Optional[list[str]]:
    if not which("git"):
        return None
    proc = run_cmd(["git", "-C", str(root), "rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        return None
    toplevel = Path(proc.stdout.strip()).resolve()
    proc = run_cmd(["git", "-C", str(toplevel), "ls-files", "-z"])
    if proc.returncode != 0:
        eprint("warning: git ls-files failed; walking the tree instead")
        return None
    rels = [p.replace("\\", "/") for p in proc.stdout.split("\0") if p]
    try:
        prefix = root.resolve().relative_to(toplevel).as_posix()
    except ValueError:
        return rels
    if prefix in {"", "."}:
        return rels
    trimmed: list[str] = []
    for path in rels:
        if path == prefix:
            trimmed.append(Path(path).name)
        elif path.startswith(prefix + "/"):
            trimmed.append(path[len(prefix) + 1 :])
    return trimmed


def walk_files(root: Path) -> list[str]:
    out: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        out.append(rel)
    return out


def path_skipped(rel: str) -> bool:
    parts = Path(rel).parts
    for part in parts:
        if part in SKIP_DIR_NAMES or part.endswith(".egg-info"):
            return True
        if part in SKIP_DIR_PREFIXES_TRACKED:
            return True
    suffix = Path(rel).suffix.lower()
    if suffix in SKIP_SUFFIXES:
        return True
    return False


def is_generated(rel: str) -> bool:
    parts = Path(rel).parts
    if "frontend" in parts and "build" in parts:
        return True
    if any(p in GENERATED_DIR_NAMES for p in parts):
        return True
    name = Path(rel).name
    if name.endswith(".min.js") or name.endswith(".min.css"):
        return True
    return False


def is_test(rel: str) -> bool:
    parts = Path(rel).parts
    if "tests" in parts or "test" in parts:
        return True
    name = Path(rel).name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith(TEST_JS_SUFFIXES):
        return True
    return False


def role_for(rel: str) -> str:
    if is_generated(rel):
        return "generated"
    if is_test(rel):
        return "tests"
    top = Path(rel).parts[0] if Path(rel).parts else ""
    if top in ("scripts", "tools"):
        return "scripts"
    if top == "config":
        return "config"
    if top in ("docs", "website", "guide"):
        return "docs"
    if top in ("src", "packages", "lib", "app"):
        return "product"
    return "other"


def fine_layer(rel: str) -> str:
    parts = Path(rel).parts
    if not parts:
        return "other"
    if is_generated(rel) and "frontend" in parts:
        pkg = parts[1] if parts[0] == "packages" and len(parts) > 1 else parts[0]
        return f"packages/{pkg}/frontend/build" if parts[0] == "packages" else "generated"
    if parts[0] == "src":
        if len(parts) >= 3 and not parts[2].endswith(".py"):
            return f"src/{parts[1]}/{parts[2]}"
        if len(parts) >= 2:
            return f"src/{parts[1]}"
        return "src"
    if parts[0] == "packages":
        pkg = parts[1] if len(parts) > 1 else "?"
        if "frontend" in parts:
            idx = parts.index("frontend")
            nxt = parts[idx + 1] if idx + 1 < len(parts) else ""
            if nxt == "src":
                return f"packages/{pkg}/frontend/src"
            if nxt == "build":
                return f"packages/{pkg}/frontend/build"
            return f"packages/{pkg}/frontend"
        return f"packages/{pkg}"
    if parts[0] == "tests":
        return "tests"
    if parts[0] in ("scripts", "tools", "config", "docs"):
        return parts[0]
    return "other"


def normalize_lang(name: str) -> str:
    key = name.strip()
    aliases = {
        "py": "Python",
        "python": "Python",
        "ts": "TypeScript",
        "typescript": "TypeScript",
        "js": "JavaScript",
        "javascript": "JavaScript",
        "tsx": "TSX",
        "jsx": "JSX",
        "md": "Markdown",
        "markdown": "Markdown",
        "yml": "YAML",
        "yaml": "YAML",
        "sh": "Shell",
        "bash": "Shell",
        "zsh": "Shell",
        "css": "CSS",
        "html": "HTML",
        "json": "JSON",
        "toml": "TOML",
        "dockerfile": "Dockerfile",
        "makefile": "Makefile",
    }
    return aliases.get(key.lower(), key)


def is_code_lang(lang: str) -> bool:
    return normalize_lang(lang).lower() not in NON_CODE_LANGS


def rel_from_tool_path(raw: str, root: Path) -> Optional[str]:
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    path = Path(text)
    root_res = root.resolve()
    try:
        if path.is_absolute():
            return path.resolve().relative_to(root_res).as_posix()
    except ValueError:
        pass
    # Already repo-relative, or cwd-relative.
    candidate = text.lstrip("./")
    abs_cand = (root / candidate).resolve()
    try:
        return abs_cand.relative_to(root_res).as_posix()
    except ValueError:
        return candidate


class FileStat:
    __slots__ = ("language", "code", "comments", "blanks")

    def __init__(
        self,
        language: str,
        code: int = 0,
        comments: int = 0,
        blanks: int = 0,
    ) -> None:
        self.language = language
        self.code = int(code)
        self.comments = int(comments)
        self.blanks = int(blanks)


def parse_tokei(payload: Any, root: Path) -> dict[str, FileStat]:
    files: dict[str, FileStat] = {}
    if not isinstance(payload, dict):
        return files
    for lang, body in payload.items():
        if lang == "Total" or not isinstance(body, dict):
            continue
        for report in body.get("reports") or []:
            name = report.get("name") or ""
            rel = rel_from_tool_path(name, root)
            if not rel:
                continue
            stats = report.get("stats") or {}
            files[rel] = FileStat(
                normalize_lang(lang),
                stats.get("code", 0),
                stats.get("comments", 0),
                stats.get("blanks", 0),
            )
    return files


def parse_scc(payload: Any, root: Path) -> dict[str, FileStat]:
    files: dict[str, FileStat] = {}
    rows = payload if isinstance(payload, list) else []
    for lang_row in rows:
        if not isinstance(lang_row, dict):
            continue
        lang = normalize_lang(str(lang_row.get("Name") or "Unknown"))
        for item in lang_row.get("Files") or []:
            if not isinstance(item, dict):
                continue
            loc = item.get("Location") or item.get("Filename") or ""
            rel = rel_from_tool_path(str(loc), root)
            if not rel:
                continue
            files[rel] = FileStat(
                normalize_lang(str(item.get("Language") or lang)),
                item.get("Code", 0),
                item.get("Comment", 0),
                item.get("Blank", 0),
            )
    return files


def parse_cloc(payload: Any, root: Path) -> dict[str, FileStat]:
    files: dict[str, FileStat] = {}
    if not isinstance(payload, dict):
        return files
    for key, body in payload.items():
        if key in {"header", "SUM"} or not isinstance(body, dict):
            continue
        if "code" not in body:
            continue
        rel = rel_from_tool_path(key, root)
        if not rel:
            continue
        files[rel] = FileStat(
            normalize_lang(str(body.get("language") or "Unknown")),
            body.get("code", 0),
            body.get("comment", 0),
            body.get("blank", 0),
        )
    return files


def parse_radon(payload: Any, root: Path) -> dict[str, FileStat]:
    files: dict[str, FileStat] = {}
    if not isinstance(payload, dict):
        return files
    for key, body in payload.items():
        if not isinstance(body, dict):
            continue
        rel = rel_from_tool_path(key, root)
        if not rel:
            continue
        # radon: sloc = source lines; comments = # comments; multi = docstrings
        files[rel] = FileStat(
            "Python",
            body.get("sloc", 0),
            int(body.get("comments", 0) or 0) + int(body.get("multi", 0) or 0),
            body.get("blank", 0),
        )
    return files


def load_json_stdout(proc: subprocess.CompletedProcess[str], label: str) -> Any:
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        eprint(f"warning: {label} exited {proc.returncode}: {err[:400]}")
        return None
    text = proc.stdout.strip()
    if not text:
        eprint(f"warning: {label} produced no stdout")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        eprint(f"warning: {label} JSON parse failed: {exc}")
        return None


def tool_version(cmd: list[str]) -> Optional[str]:
    proc = run_cmd(cmd, timeout=15)
    if proc.returncode != 0:
        return None
    line = (proc.stdout or proc.stderr).strip().splitlines()
    return line[0].strip() if line else None


def batched(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def collect_tokei(root: Path, rels: list[str]) -> dict[str, FileStat]:
    exe = which("tokei")
    if not exe:
        eprint("warning: tokei not installed")
        return {}
    merged: dict[str, FileStat] = {}
    for chunk in batched(rels, 400):
        proc = run_cmd([exe, "--output", "json", "--no-ignore", *chunk], cwd=root)
        payload = load_json_stdout(proc, "tokei")
        if payload is None:
            continue
        merged.update(parse_tokei(payload, root))
    return merged


def collect_scc(root: Path, rels: list[str]) -> dict[str, FileStat]:
    exe = which("scc")
    if not exe:
        eprint("warning: scc not installed")
        return {}
    merged: dict[str, FileStat] = {}
    for chunk in batched(rels, 400):
        proc = run_cmd(
            [exe, "--format", "json", "--by-file", "--no-cocomo", *chunk],
            cwd=root,
        )
        payload = load_json_stdout(proc, "scc")
        if payload is None:
            continue
        merged.update(parse_scc(payload, root))
    return merged


def collect_cloc(root: Path, rels: list[str]) -> dict[str, FileStat]:
    exe = which("cloc")
    if not exe:
        eprint("warning: cloc not installed")
        return {}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(rels))
        list_path = handle.name
    try:
        proc = run_cmd(
            [exe, "--json", "--by-file", "--quiet", f"--list-file={list_path}"],
            cwd=root,
            timeout=300,
        )
    finally:
        Path(list_path).unlink(missing_ok=True)
    payload = load_json_stdout(proc, "cloc")
    return parse_cloc(payload, root) if payload is not None else {}


def collect_radon(root: Path, py_rels: list[str]) -> dict[str, FileStat]:
    exe = which("radon")
    cmd0: list[str]
    if exe:
        cmd0 = [exe]
    else:
        cmd0 = [sys.executable, "-m", "radon"]
        probe = run_cmd(cmd0 + ["--version"], timeout=15)
        if probe.returncode != 0:
            eprint("warning: radon not installed")
            return {}
    merged: dict[str, FileStat] = {}
    for chunk in batched(py_rels, 200):
        proc = run_cmd(cmd0 + ["raw", "-j", *chunk], cwd=root, timeout=180)
        payload = load_json_stdout(proc, "radon")
        if payload is None:
            continue
        merged.update(parse_radon(payload, root))
    return merged


def median_int(values: Iterable[Optional[int]]) -> Optional[int]:
    nums = [int(v) for v in values if v is not None]
    if not nums:
        return None
    nums.sort()
    if len(nums) % 2 == 1:
        return nums[len(nums) // 2]
    # Even count: pick the lower middle so the estimate stays a real tool value
    # when two counters agree-ish; mean of two middles otherwise.
    hi = nums[len(nums) // 2]
    lo = nums[len(nums) // 2 - 1]
    return int(round(statistics.median([lo, hi])))


def agg_key(layer: str, language: str) -> tuple[str, str]:
    return (layer, language)


def empty_bucket() -> dict[str, Any]:
    return {
        "files": set(),
        "tokei": {"code": 0, "comments": 0, "blanks": 0, "files": 0},
        "scc": {"code": 0, "comments": 0, "blanks": 0, "files": 0},
        "cloc": {"code": 0, "comments": 0, "blanks": 0, "files": 0},
        "radon": {"code": 0, "comments": 0, "blanks": 0, "files": 0},
    }


def add_stat(bucket: dict[str, Any], tool: str, rel: str, stat: FileStat) -> None:
    bucket["files"].add(rel)
    slot = bucket[tool]
    slot["code"] += stat.code
    slot["comments"] += stat.comments
    slot["blanks"] += stat.blanks
    slot["files"] += 1


def fmt_num(n: Optional[int]) -> str:
    if n is None:
        return "—"
    return f"{n:,}"


def fmt_range(lo: Optional[int], hi: Optional[int]) -> str:
    if lo is None or hi is None:
        return "—"
    if lo == hi:
        return fmt_num(lo)
    return f"{lo:,}–{hi:,}"


def estimate_from_bucket(bucket: dict[str, Any]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    vals = [bucket[t]["code"] for t in CODE_TOOLS if bucket[t]["files"] or bucket[t]["code"]]
    # A layer may have files in one tool and zero in another if a parser missed them.
    present = []
    for tool in CODE_TOOLS:
        if bucket[tool]["files"] > 0 or bucket[tool]["code"] > 0:
            present.append(bucket[tool]["code"])
    if not present:
        return None, None, None
    return median_int(present), min(present), max(present)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def serialize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    est, lo, hi = estimate_from_bucket(bucket)
    return {
        "files": len(bucket["files"]),
        "tokei": {k: bucket["tokei"][k] for k in ("code", "comments", "blanks", "files")},
        "scc": {k: bucket["scc"][k] for k in ("code", "comments", "blanks", "files")},
        "cloc": {k: bucket["cloc"][k] for k in ("code", "comments", "blanks", "files")},
        "radon": {k: bucket["radon"][k] for k in ("code", "comments", "blanks", "files")},
        "estimate": est,
        "range": [lo, hi],
    }


def row_from_bucket(label: str, extra: str, bucket: dict[str, Any]) -> list[str]:
    est, lo, hi = estimate_from_bucket(bucket)
    comments = bucket["tokei"]["comments"] or bucket["scc"]["comments"]
    blanks = bucket["tokei"]["blanks"] or bucket["scc"]["blanks"]
    files_n = max(
        len(bucket["files"]),
        bucket["tokei"]["files"],
        bucket["scc"]["files"],
        bucket["cloc"]["files"],
    )
    return [
        label,
        extra,
        fmt_num(bucket["tokei"]["code"] if bucket["tokei"]["files"] or bucket["tokei"]["code"] else None),
        fmt_num(bucket["scc"]["code"] if bucket["scc"]["files"] or bucket["scc"]["code"] else None),
        fmt_num(bucket["cloc"]["code"] if bucket["cloc"]["files"] or bucket["cloc"]["code"] else None),
        fmt_num(bucket["radon"]["code"] if bucket["radon"]["files"] or bucket["radon"]["code"] else None),
        fmt_num(est),
        fmt_range(lo, hi),
        fmt_num(comments),
        fmt_num(blanks),
        fmt_num(files_n),
    ]


def measure(root: Path) -> dict[str, Any]:
    root = root.resolve()
    tracked = git_ls_files(root)
    source = "git" if tracked is not None else "walk"
    rels = tracked if tracked is not None else walk_files(root)
    rels = [r.replace("\\", "/") for r in rels if not path_skipped(r)]
    rel_set = set(rels)

    versions = {
        "tokei": tool_version(["tokei", "--version"]) if which("tokei") else None,
        "scc": tool_version(["scc", "--version"]) if which("scc") else None,
        "cloc": tool_version(["cloc", "--version"]) if which("cloc") else None,
        "radon": tool_version(["radon", "--version"])
        if which("radon")
        else tool_version([sys.executable, "-m", "radon", "--version"]),
    }

    tokei_files = collect_tokei(root, rels)
    scc_files = collect_scc(root, rels)
    cloc_files = collect_cloc(root, rels)
    py_rels = [r for r in rels if r.endswith(".py") and not is_generated(r)]
    radon_files = collect_radon(root, py_rels)

    def keep(rel: str) -> bool:
        return rel in rel_set

    layers: dict[tuple[str, str], dict[str, Any]] = defaultdict(empty_bucket)
    roles: dict[tuple[str, str], dict[str, Any]] = defaultdict(empty_bucket)
    role_code: dict[str, dict[str, Any]] = defaultdict(empty_bucket)
    product_python = empty_bucket()
    product_all = empty_bucket()
    maintained = empty_bucket()

    def consider(tool: str, mapping: dict[str, FileStat]) -> None:
        for rel, stat in mapping.items():
            if not keep(rel):
                continue
            layer = fine_layer(rel)
            role = role_for(rel)
            add_stat(layers[agg_key(layer, stat.language)], tool, rel, stat)
            add_stat(roles[agg_key(role, stat.language)], tool, rel, stat)
            if not is_code_lang(stat.language):
                continue
            add_stat(role_code[role], tool, rel, stat)
            if role == "product":
                add_stat(product_all, tool, rel, stat)
                if stat.language == "Python":
                    add_stat(product_python, tool, rel, stat)
            if role in {"product", "tests", "scripts"}:
                add_stat(maintained, tool, rel, stat)

    consider("tokei", tokei_files)
    consider("scc", scc_files)
    consider("cloc", cloc_files)
    consider("radon", radon_files)

    return {
        "root": str(root),
        "source": source,
        "tracked_files": len(rels),
        "tools": versions,
        "layers": {
            f"{layer}::{lang}": serialize_bucket(bucket)
            for (layer, lang), bucket in sorted(layers.items())
        },
        "roles": {
            f"{role}::{lang}": serialize_bucket(bucket)
            for (role, lang), bucket in sorted(roles.items())
        },
        "headlines": {
            "product": serialize_bucket(product_all),
            "maintained": serialize_bucket(maintained),
            "python_product": serialize_bucket(product_python),
        },
        "_buckets": {
            "layers": dict(layers),
            "role_code": dict(role_code),
            "product_all": product_all,
            "maintained": maintained,
            "product_python": product_python,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    buckets = result["_buckets"]
    versions = result["tools"]
    lines: list[str] = []
    lines.append(f"# SLOC comparison: `{result['root']}`")
    lines.append("")
    tool_bits = []
    for name in ("tokei", "scc", "cloc", "radon"):
        ver = versions.get(name)
        tool_bits.append(f"{name} {ver}" if ver else f"{name} (missing)")
    lines.append("Counters: " + "; ".join(tool_bits))
    lines.append(
        f"File list: **{result['tracked_files']:,}** paths from `{result['source']}` "
        "(skipping vendored/cache/archive/artifacts)."
    )
    lines.append("")
    lines.append("Estimate is the **median** of tokei / scc / cloc **code** columns. ")
    lines.append("Range is min–max of those three. radon is Python SLOC only (docstrings not counted as code) and is a cross-check, not averaged into the headline.")
    lines.append("Markdown, JSON, YAML, TOML, XML, SVG, and similar are excluded from role/headline code totals.")
    lines.append("")

    lines.append("## Role summary (code)")
    lines.append("")
    headers = [
        "Role",
        "Lang",
        "tokei",
        "scc",
        "cloc",
        "radon",
        "estimate",
        "range",
        "comments",
        "blanks",
        "files",
    ]
    rows: list[list[str]] = []
    for role in ROLE_ORDER:
        bucket = buckets["role_code"].get(role)
        if not bucket or not bucket["files"]:
            continue
        rows.append(row_from_bucket(role, "code langs", bucket))
    lines.append(markdown_table(headers, rows))
    lines.append("")

    headlines = result["headlines"]
    py = headlines["python_product"]
    product = headlines["product"]
    maintained = headlines["maintained"]
    lines.append("## Headline estimates")
    lines.append("")
    lines.append(
        f"1. **Substantive product SLOC** — {fmt_num(product['estimate'])} "
        f"(range {fmt_range(product['range'][0], product['range'][1])}). "
        "Application source under src/packages/lib/app, including frontend `src`, excluding tests and generated `build`."
    )
    lines.append(
        f"2. **Maintained SLOC** — {fmt_num(maintained['estimate'])} "
        f"(range {fmt_range(maintained['range'][0], maintained['range'][1])}). "
        "Product + tests + scripts/tools."
    )
    trio = py["estimate"]
    radon_n = py["radon"]["code"] if py["radon"]["files"] or py["radon"]["code"] else None
    delta_note = ""
    if trio and radon_n:
        delta_pct = abs(radon_n - trio) / trio * 100
        if delta_pct > 10:
            delta_note = (
                f" radon is {delta_pct:.0f}% {'lower' if radon_n < trio else 'higher'} "
                "than the trio median, so it is **not** folded into the headline."
            )
        else:
            delta_note = f" radon agrees within {delta_pct:.0f}%."
    lines.append(
        f"3. **Python-only product SLOC** — trio median {fmt_num(trio)} "
        f"(range {fmt_range(py['range'][0], py['range'][1])}); "
        f"radon SLOC {fmt_num(radon_n)}.{delta_note}"
    )
    lines.append("")

    lines.append("## Layer detail")
    lines.append("")
    detail_rows: list[list[str]] = []
    layer_items: list[tuple[str, str, dict[str, Any]]] = []
    for (layer, lang), bucket in buckets["layers"].items():
        if not bucket["files"]:
            continue
        layer_items.append((layer, lang, bucket))

    def layer_sort(item: tuple[str, str, dict[str, Any]]) -> tuple:
        layer, lang, bucket = item
        role_guess = "other"
        for role in ROLE_ORDER:
            if layer == role or layer.startswith(role + "/") or (
                role == "product" and layer.startswith(("src/", "packages/", "lib/", "app/"))
            ) or (role == "product" and layer in {"src", "packages", "lib", "app"}):
                role_guess = role
                break
        if layer.startswith("src/"):
            role_guess = "product"
        elif layer.startswith("packages/") and "/build" in layer:
            role_guess = "generated"
        elif layer.startswith("packages/"):
            role_guess = "product"
        elif layer in ROLE_ORDER:
            role_guess = layer
        return (ROLE_ORDER.index(role_guess) if role_guess in ROLE_ORDER else 99, layer, lang)

    for layer, lang, bucket in sorted(layer_items, key=layer_sort):
        if not is_code_lang(lang) and fine_layer_role(layer) not in {"docs", "config", "other"}:
            # still show docs/config non-code; skip json fixtures under tests/src
            if fine_layer_role(layer) in {"product", "tests", "scripts", "generated"}:
                continue
        detail_rows.append(row_from_bucket(layer, lang, bucket))
    lines.append(markdown_table(headers, detail_rows))
    lines.append("")
    lines.append("comments/blanks columns prefer tokei, then scc.")
    return "\n".join(lines) + "\n"


def fine_layer_role(layer: str) -> str:
    if layer in ROLE_ORDER:
        return layer
    if layer.startswith("src/") or layer in {"src", "packages", "lib", "app"}:
        return "product"
    if layer.startswith("packages/") and "/build" in layer:
        return "generated"
    if layer.startswith("packages/"):
        return "product"
    if layer.startswith("tests"):
        return "tests"
    return "other"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare SLOC using tokei, scc, cloc, and radon.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root (default: cwd)")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install missing tokei/scc/cloc via Homebrew and radon via pip, then measure",
    )
    parser.add_argument(
        "--json",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Write JSON to PATH, or stdout if PATH is omitted / '-'",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="With --json, skip the markdown table",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.install:
        install_tools()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        eprint(f"error: not a directory: {root}")
        return 2
    result = measure(root)
    public = {k: v for k, v in result.items() if not k.startswith("_")}
    if not args.json_only:
        sys.stdout.write(render_markdown(result))
    if args.json is not None:
        blob = json.dumps(public, indent=2, sort_keys=True)
        if args.json in {"-", ""}:
            if not args.json_only:
                sys.stdout.write("\n## JSON\n\n```json\n")
                sys.stdout.write(blob)
                sys.stdout.write("\n```\n")
            else:
                sys.stdout.write(blob + "\n")
        else:
            out = Path(args.json).expanduser()
            out.write_text(blob + "\n", encoding="utf-8")
            eprint(f"wrote JSON: {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        eprint(f"error: command timed out: {exc.cmd}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
