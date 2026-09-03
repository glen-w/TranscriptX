# TranscriptX SLOC estimate (2026-09-02)

**Maintainer assessment** under [docs/reviews/](index.md). Dated snapshot, not a contract. Hosted at `/guide/reviews/sloc-estimate-2026-09-02/` after `make docs`.

Measured with `tokei` 14.0.0, `scc` 4.0.0, `cloc` 2.08, and `radon` 6.0.1 via [`scripts/count_sloc.py`](../../scripts/count_sloc.py) (also bundled in the personal Cursor skill `~/.cursor/skills/count-sloc/`). Git-tracked files only; 2,873 paths after dropping `archive/`, `artifacts/`, vendored/cache trees, and binary assets.

This is **source lines of code** (comments and blanks stripped). Markdown, JSON, YAML, and TOML are not treated as code in the headlines.

---

## Headlines

Estimate = **median** of tokei / scc / cloc **code** columns. Range = min–max of those three. radon is Python-only and is a cross-check, not averaged in.

| Estimate | SLOC | Range |
|----------|-----:|-------|
| **Substantive product** — app source under `src/` + `packages/` source (including frontend `src`); no tests, no generated `build/` | **193,818** | 193,029–210,704 |
| **Maintained** — product + tests + scripts/tools | **360,257** | 359,047–382,290 |
| **Python-only product** | **192,982** | 192,196–209,868 |

radon Python product SLOC is **194,174** (within **1%** of the trio median). tokei is the high outlier (it counts more docstring-adjacent lines as code). scc and cloc agree closely; the median follows them.

Use **~194k** as the product figure and **~360k** as the maintained figure. Quote the range if the number will be compared later.

---

## Role summary (code languages only)

| Role | tokei | scc | cloc | radon | estimate | range |
|------|------:|----:|-----:|------:|---------:|-------|
| product | 210,704 | 193,818 | 193,029 | 194,174 | **193,818** | 193,029–210,704 |
| tests | 165,038 | 160,211 | 160,055 | 160,178 | **160,211** | 160,055–165,038 |
| scripts | 6,548 | 6,228 | 5,963 | 5,796 | **6,228** | 5,963–6,548 |
| generated (`frontend/build`) | 512 | 512 | 326 | — | 512 | 326–512 |
| other (Dockerfiles, Makefile, CSS at repo root, …) | 456 | 456 | 474 | — | 456 | 456–474 |

Tests are almost as large as product (~160k vs ~194k). That is a real maintenance surface, not an artifact of the counters.

Tracked JSON elsewhere is another **~150–230k** physical/code-ish lines (fixtures, schemas, examples). It is **not** in the headlines.

---

## Product breakdown

Python unless noted. Estimate = median of tokei / scc / cloc.

| Slice | estimate | range | files |
|-------|---------:|-------|------:|
| `src/transcriptx/core` | **120,615** | 120,368–131,260 | 775 |
| `src/transcriptx/web` | **44,550** | 44,297–48,031 | 237 |
| `src/transcriptx/services` | **10,877** | 10,796–11,323 | 71 |
| `src/transcriptx/io` | **7,423** | 7,423–8,533 | 77 |
| `src/transcriptx/app` | **5,744** | 5,744–6,285 | 47 |
| `src/transcriptx/export` | **2,270** | 2,260–2,384 | 19 |
| `src/transcriptx/utils` | **1,386** | 1,242–1,894 | 6 |
| `src/transcriptx` (package root) | 23 | 23–55 | 2 |
| `packages/…` Python | 94 | 43–102 | 1 |
| frontend `src` (TypeScript + CSS) | **886** | 886 | 5 |

`core` is ~62% of product SLOC; `web` is ~23%. Frontend source is small; committed `frontend/build` (~512 lines) is generated and excluded from the product headline.

---

## Calibration against older counts

| Source | What it counts | Figure |
|--------|----------------|--------|
| This run | SLOC (comments/blanks stripped; no markdown/JSON) | product **193,818**; core **120,615**; web **44,550** |
| [`scripts/log_code_size.py`](../../scripts/log_code_size.py) (same day) | raw physical lines in `src` + `config` + `scripts`, including markdown/JSON | **255,570** lines / 1,294 files |
| [stocktake 2026-07-17](../dev/stocktake_2026-07-17.md) | approximate physical LOC | `core/` ~94k; `web/` ~28k |

The July stocktake is **low** relative to current SLOC (`core` ~121k, `web` ~45k): the tree grew, and that note was a coarser physical-line sketch, not a comment-stripped count. `log_code_size.py` remains useful as a crude time series; **do not** use it as the substantive-code estimate.

---

## Method (short)

1. `git ls-files`, then drop `archive/`, `artifacts/`, `node_modules/`, `dist/`, `*.egg-info`, caches, and binary suffixes.
2. Run tokei, scc, cloc, and radon on that list; bucket by role (`product` / `tests` / `scripts` / `docs` / `generated` / `other`) and by directory slice.
3. Headline languages exclude markdown, JSON, YAML, TOML, XML, SVG, and similar.
4. `role=product` is `src/`, `packages/` source, `lib/`, `app/`. `*.test.ts` and `tests/` are tests. `frontend/build` is generated.

Re-run:

```bash
python3 scripts/count_sloc.py --root .
# other repos:
python3 ~/.cursor/skills/count-sloc/scripts/count_sloc.py --root .
```

`--install` adds missing Homebrew `tokei`/`scc`/`cloc` and pip `radon`. `--json PATH` writes the machine-readable totals. Radon is a host tool, not a project dependency.

---

## Related

- Runner: [`scripts/count_sloc.py`](../../scripts/count_sloc.py)
- Inventory row: [`docs/dev/script_inventory_1_0.md`](../dev/script_inventory_1_0.md)
- Architecture (same day): [`architecture-review-2026-09-02.md`](architecture-review-2026-09-02.md)
- Older size sketch: [`docs/dev/stocktake_2026-07-17.md`](../dev/stocktake_2026-07-17.md)
