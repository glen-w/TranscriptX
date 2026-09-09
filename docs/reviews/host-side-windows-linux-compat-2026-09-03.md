# Host-side Windows / Linux compatibility (2026-09-03)

**Maintainer assessment** under [docs/reviews/](index.md). Dated snapshot, not a contract. Where this disagrees with contracts or `src/`, **code and contracts win**. Hosted at `/guide/reviews/host-side-windows-linux-compat-2026-09-03/` after `make docs`.

**Parked (2026-09-03):** do **not** implement Windows/Linux host-script portability before **1.0**. Tracked as 1.x theme **G3** in [ROADMAP.md](../ROADMAP.md#g3-host-companion-scripts-on-windows--linux-parked-post-10). 1.0 stays macOS-typical `inbox-watch` / whispermlx + Docker (WSL2 on Windows).

Static reconstruction of the **host-side** TranscriptX tree (processes that run *outside* `transcriptx-web`) as of 2026-09-03. No Windows or Linux host was executed. CI is `ubuntu-latest` only (`.github/workflows/ci.yml`). Where docs and code disagree, **code wins**.

Claimed OS policy already on file: [install_verification_matrix.md](../runtime/install_verification_matrix.md) (macOS supported-with-caveats, Linux supported, Windows best-effort / WSL2+Docker) and [release_ops_support_1_0.md](../dev/release_ops_support_1_0.md) (macOS and Linux for supported cells; Windows best-effort). This review checks whether **host companions** match that story.

---

## Verdict

The analysis app in Docker is a Linux container on every host OS. The **host companions** that feed it audio and transcripts are **macOS-shaped**.

| Surface | Linux host | Windows host | Notes |
|---------|------------|--------------|--------|
| `scripts/inbox-watch.py` core (poll, ffmpeg convert, copy, `--admit`) | **Mostly portable Python** | **Runnable with gaps** | pathlib + argv subprocess; Unix venv discovery and Unix install docs |
| Audio convert + STT via inbox-watch | **Blocked by whispermlx** | **Blocked by whispermlx** | `watch_audio` requires `whispermlx-missing`, which requires the `whispermlx` binary |
| Transcript-copy / `--admit` only | **Should work** | **Admit venv lookup broken** | `--no-watch-audio --watch-transcripts`; Windows lacks `Scripts\python.exe` candidates |
| `scripts/whispermlx-missing.py` | **Not a Linux STT path** | **Not a Windows STT path** | Apple MLX; flags are whispermlx-specific |
| Transcribe Audio copyable commands | **WhisperX Docker snippet is the Linux path** | **Bash-only; will not paste into cmd/PowerShell** | `shlex.quote`, `source`, `mkdir -p` |
| `scripts/macos/` launchd agent | **None** | **None** | Hardcoded to one macOS user even on Darwin |
| `./transcriptx.sh` native GUI | **Intended** | **No** | bash + `.transcriptx/bin/activate` |
| In-app G2 watcher | **OK native Linux; flaky in Docker bind mounts** | **OK native; flaky in Docker Desktop** | `watchdog.Observer` (inotify / ReadDirectoryChangesW), not polling |
| Docker Compose bind mounts | **Supported; UID interpolation trap** | **Docker Desktop + WSL2** | `${UID:-1000}` often not in the process env |

**Product-honest reading:** Linux users are expected to run analysis in Docker and STT via the WhisperX (or Whisper-WebUI) **copyable** recipes, then Import Transcript. Windows users are expected to use WSL2 + Docker and the same import path. The host inbox watcher is documented as a Mac companion (`directory_watcher.md`: “runs on the Mac host”). That is accurate. It is **not** a cross-platform host daemon.

---

## What “outside the container” actually is

```{mermaid}
flowchart TB
  subgraph host [Host OS process]
    Inbox[USB / drop folder]
    IW[inbox-watch.py]
    WM[whispermlx-missing.py]
    MLX[whispermlx binary]
    FFMPEG[ffmpeg]
    Admit["python -m transcriptx.admit_originals"]
    CmdGen[Copyable bash from Transcribe Audio]
    WX[WhisperX docker run]
  end
  subgraph ctr [transcriptx-web Linux container]
    GUI[Streamlit]
    G2[G2 watchdog Observer]
    Import[admit_and_register]
  end
  Inbox --> IW
  IW --> FFMPEG
  IW --> WM
  WM --> MLX
  IW --> Admit
  CmdGen --> MLX
  CmdGen --> WX
  MLX -->|originals JSON| Import
  WX -->|originals JSON| Import
  IW -->|copy transcripts| Import
  G2 -->|in-process| Import
  GUI --> CmdGen
```

**In-process (inside whatever runs Streamlit):** Settings → Watcher (G2). If the operator uses Compose, that is the Linux container. If they use `./transcriptx.sh`, that is native host Python.

**Out-of-process host scripts (never imported by Streamlit):**

| Path | Role | Inventory platform |
|------|------|-------------------|
| `scripts/inbox-watch.py` | Poll inbox → ffmpeg MP3 + copy transcripts; optional admit | “macOS typical” |
| `scripts/whispermlx-missing.py` | Batch STT for MP3s missing JSON | “Apple Silicon typical” |
| `scripts/macos/inbox-watch-agent.sh` + plist | login `--watch` | Darwin only |
| `src/transcriptx/services/transcription/command_gen.py` | Copyable host commands (not executed) | bash / macOS / Linux Docker recipes |
| `transcriptx.sh` | Native venv + Streamlit | macOS/Linux |
| `scripts/audio_merge.py` / `audio_preprocess.py` | ffmpeg helpers (also callable from GUI Tools) | “any” + ffmpeg |
| `scripts/workspace_backup.py` | ZIP backup/restore | pathlib ZIP |

Maintainer bash (`Makefile`, `scripts/release/*.sh`, `scripts/docker-smoke-test.sh`) is Unix/CI. Out of scope for an unfamiliar Windows operator; listed only where it blocks Linux/Windows **product** use.

---

## A. `inbox-watch.py`

~1.7k lines, stdlib only, does not import `transcriptx`. Optional `--admit` **subprocesses** `python -m transcriptx.admit_originals`.

### What is already portable

- `pathlib.Path`, `expanduser()`, `mkdir(parents=True)`, `os.replace` for the `.mp3.partial` → dest hop (same-volume atomic replace on POSIX and NT).
- `subprocess.run(list_of_args)` — no `shell=True`.
- Classification and stem matching use `.suffix.lower()` / `.stem.lower()` (`classify_path`, `find_stem_match`). Windows `.WAV` / `.JSON` from recorders is handled.
- Dotfile skip (`path.name.startswith(".")`) hides the convert temp `.inbox-watch.{stem}.mp3.partial`.
- Poll loop (`--watch` + `time.sleep`) rather than inotify. Correct choice for USB volumes that appear and disappear (`wait` + empty cycles when the inbox path is missing).
- `shutil.which("ffmpeg")` (finds `ffmpeg.exe` on Windows if PATH/PATHEXT is set).
- `KeyboardInterrupt` → clean stop; failed convert unlinks the partial.
- stdout/stderr `reconfigure(line_buffering=True)` with `OSError`/`ValueError` swallowed (Windows consoles that refuse reconfigure).

### Linux — expected behaviour

**Convert + copy + admit, given ffmpeg + a native TranscriptX venv, should run.** The script does not call Darwin APIs.

**STT after convert will not, unless a `whispermlx` binary exists.** `watch_audio` (default on) **requires** `whispermlx-missing` even when every MP3 already has JSON (`find_whispermlx_missing` / `maybe_run_missing`). There is no hook for WhisperX, faster-whisper, or a no-op. Practical Linux use today:

```bash
python3 scripts/inbox-watch.py --once --no-watch-audio --watch-transcripts \
  --inbox … --transcripts …/originals
# optional: --admit --admit-python .transcriptx/bin/python
```

Audio conversion without STT is also unused: converting always tries to invoke missing afterwards when `watch_audio` is on.

`find_admit_python` looks at Unix venv layouts only:

```1033:1037:scripts/inbox-watch.py
        for rel in (
            ".transcriptx/bin/python",
            ".transcriptx/bin/python3",
            ".venv/bin/python",
        ):
```

On Linux that matches `transcriptx.sh` / a normal venv. On Windows those paths never exist (`Scripts\python.exe`). `--admit-python` still works if the operator passes it explicitly.

Install docs (`host-stt.md`, module docstring) use `install -m 755` and `~/.local/bin` — fine on Linux, absent on Windows.

No systemd user unit exists. `--once` is cron-shaped; `--watch` is a long-running foreground process. The macOS agent is not a template for `transcriptx-inbox-watch.service`.

USB inbox paths: docs and `.env.example` show `/Volumes/USB-DISK/RECORD`. Linux equivalents are `/media/$USER/…` or `/run/media/$USER/…`. The script does not care; only examples do.

### Windows — extra gaps

| Issue | Why it bites |
|-------|----------------|
| Shebang `#!/usr/bin/env python3` | cmd.exe does not run extensionless copies; use `py -3 scripts\inbox-watch.py`. |
| `install -m 755` → `~\.local\bin\inbox-watch` | No GNU `install`; no shebang execution. After copy-without-`.py`, `build_missing_cmd` treats the sibling as a binary (`suffix != ".py"`) and `CreateProcess` fails with WinError 193. |
| `find_admit_python` | Never finds `.transcriptx\Scripts\python.exe`. Error text still says `.transcriptx/bin/python`. |
| `os.replace(partial, dest)` | Fails with `PermissionError` if Defender / a player has the dest MP3 open. POSIX replace is more forgiving. |
| `src.unlink()` / `shutil.move` after convert | USB recorders and Explorer previews often hold the source; delete/move then fails. FAT/exFAT + AV is the usual USB inbox. |
| `wait_until_stable` uses size + `st_mtime_ns` | FAT mtime granularity is 2s. Size still changing saves you; preallocated files that fill in place can look “stable” early. |
| Hidden files | Only names starting with `.` are skipped. `desktop.ini` is ignored by extension; `Thumbs.db` is not an audio/transcript ext so it is scanned then `ignore`. Windows hidden *attribute* is not read. |
| `is_same_or_under` / `Path.resolve().relative_to` | Case-sensitive. `path_canonical.canonicalise_path` uses `os.path.normcase` on Windows; inbox-watch layout checks do not. Mixed `C:\Inbox` vs `c:\inbox` can false-negative containment. |
| Console encoding | Recorders with non-cp1252 names can `UnicodeEncodeError` on older Windows consoles unless UTF-8 is on. |
| No Task Scheduler / NSSM / Windows service sample | `--watch` is a console loop. |

`chmod(0o600)` on saved JSON is a no-op besides the read-only bit on NT; harmless.

`wait_for_directory` is defined but unused; `--watch` inlines the same idea. Not an OS bug.

### Coupling that is not OS-specific but blocks non-Mac STT

`build_missing_cmd` always passes `--source` / `--transcripts` to whispermlx-missing. There is no `--transcribe-cmd` or provider switch. Until that exists, **inbox-watch audio mode is a macOS STT pipeline**, not a generic convert+queue.

---

## B. `whispermlx-missing.py`

Same portability profile as inbox-watch for paths/config/chmod/`os.replace`, plus:

- `shutil.which("whispermlx")` — binary name, Apple MLX stack. `WhisperMLXProvider.is_available` **fails closed** unless `sys.platform == "darwin"` (`whispermlx_provider.py`).
- `shlex.join` for dry-run command printing (POSIX quoting; cosmetic on Windows).
- `subprocess.run(..., text=True)` without `encoding="utf-8"` — Windows `text=True` uses the locale encoding; whispermlx stderr with UTF-8 can throw on decode if anyone ever ran it there.
- Live run **requires** a whispermlx binary (dry-run does not). Extra args (`--output_dir`, `--diarize`, `-f`) are whispermlx CLI, not WhisperX.

Linux/Windows operators who want bulk “skip existing JSON” need a different driver (or a wrapper that only pretends to be whispermlx). The Transcribe Audio page and `host-stt.md` already say macOS host / not inside the analysis container. They do **not** say “this script is useless on Linux”; the failure mode is a missing binary at runtime.

---

## C. macOS login agent (not portable, not a template)

`scripts/macos/inbox-watch-agent.sh` and `com.transcriptx.inbox-watch.plist` are **machine-local**, not repo-portable:

- Absolute Python: `/Users/89298/.pyenv/versions/3.10.13/bin/python3`
- Absolute repo, logs, and `TRANSCRIPTX_*` dirs under `/Users/89298/Documents/…`
- PATH: pyenv shims + Homebrew
- Comment: waits for `/Volumes/USB-DISK/RECORD`

Even another Mac checkout cannot load this plist unchanged. Linux needs a systemd user unit (or cron `--once`). Windows needs Task Scheduler. None exist. Docs call this “optional macOS login agent” — correct, but the files are a private LaunchAgent checked into the tree.

---

## D. Copyable host commands (`command_gen.py`)

Streamlit **never executes** these. The operator pastes them into a host terminal. Every generator emits **POSIX shell**:

| Helper | Constructs |
|--------|------------|
| `build_whispermlx_single` / `_batch_loop` | `set -a; source …; mkdir -p; for f in …; command -v` |
| `build_whispermlx_missing` | `whispermlx-missing …` + `install -m 755` / `python3` notes |
| `build_whisperx_docker` | `mkdir -p`, `docker run \` line continuations, `-v host:container` |
| `build_whisper_webui_docker` | `if [ ! -d ]; git clone; docker run -d` |

`_q()` is `shlex.quote` (single-quote POSIX). PowerShell / cmd quoting is different. Git Bash or WSL can run the snippets on a Windows box; Windows Terminal + PowerShell cannot.

Further Windows/Linux nits in the **same** module:

- `params.input_path.rstrip("/")` then `.endswith((".mp3", …))` to choose single-file vs folder loop. Backslash paths (`C:\rec\a.mp3`) still end with `.mp3`, but **`.MP3` does not match** (no `.lower()`). Windows Explorer often shows uppercase extensions; the generator would emit a folder loop for a single file.
- `rstrip("/")` does not strip `\`. WhisperX `-v C:\data\audio\:/audio` is a broken bash mount; Docker Desktop PowerShell wants a different spelling; Git Bash wants `/c/data/audio`.
- Default WebUI clone dir `$HOME/Whisper-WebUI` is POSIX.
- `looks_like_container_install_path` only treats `/opt/venv` as the Docker install. Fine.

**Linux GPU STT** is this WhisperX `docker run` recipe (`docs/recipes/whisperx/`), not inbox-watch. That path is the one that matches “Linux supported” for transcription, and it is already bash/Linux-shaped.

---

## E. Native launcher `transcriptx.sh`

Supported inventory row: macOS/Linux. Concrete Unix assumptions:

- `#!/bin/bash`, `source .env`, `source .transcriptx/bin/activate`
- `command -v python3.10` (not `python` / `py -3.10`)
- `write_install_profile` → `$HOME/.config/transcriptx` (XDG; no `%APPDATA%`)
- `which python`, `rm -rf`, ANSI `echo -e`

Windows native GUI is `python -m venv .venv` + `.venv\Scripts\activate` as mentioned once in [installation-advanced.md](../runtime/installation-advanced.md). There is no `transcriptx.ps1` / `transcriptx.bat`. Compose remains the advertised Windows path.

Linux: this script is the native path. It will not help inbox-watch find whispermlx.

---

## F. In-app G2 watcher (runs wherever Streamlit runs)

Not a host script, but it is the other “watcher”, and it **does** run outside Docker on a native install.

`WatchObserver` constructs `watchdog.observers.Observer()` — native backends:

| OS | Backend | USB / network / Docker bind |
|----|---------|------------------------------|
| Linux native | inotify | Often **silent** on NFS, SMB, some FUSE; USB ext4/exFAT usually OK |
| Linux **in Compose** watching a **host** drop folder | inotify **inside the VM** | Docker Desktop (Mac/Windows) virtiofs/osxfs frequently **does not deliver inotify** for host-side creates. Native Linux docker bind-mounts are more reliable. |
| Windows native | `ReadDirectoryChangesW` | USB usually OK; SMB mixed |
| macOS native | FSEvents | USB OK; Docker bind from host → container is the weak case |

There is **no `PollingObserver` fallback**. Debounce key is `str(path)` (no `normcase`). G2 never converts audio (`auto_transcribe` rejected until theme H).

This is why `directory_watcher.md` points Mac operators at host `inbox-watch` for convert+STT. On Linux Docker, **the same virtiofs inotify hole** exists for G2 if they watch a Desktop-mounted inbox. Host-side `inbox-watch` polling would still be the robust drop-folder design — if STT were not whispermlx-only.

---

## G. Shared host-adjacent utilities

### File locking — `src/transcriptx/core/utils/file_lock.py`

Intentional NT/POSIX split: `msvcrt.locking` vs `fcntl.flock`. Used by stores when `--admit` or G2 runs **on the host** (native) or in the container.

Windows caveats: byte-range mandatory lock; `unlink` of a held `.lock` often `PermissionError`; SMB/USB locks are weaker; `is_locked()` is racy. Linux `flock` is advisory and matches the Darwin comment about re-entrancy. Fine for a single-user workspace; not a distributed lock.

### Path identity

`path_canonical.canonicalise_path` **does** `os.path.normcase` on Darwin and NT. `is_under_directory` (`import_admission.py`) and inbox-watch `is_same_or_under` **do not**. Folder-import / G2 “must not watch the library” checks can disagree with Windows short/long or case variants.

`path_safety.assert_safe_relpath` rejects `X:` and `\\` — correct for untrusted relative names; not used as a host-inbox sanitiser.

### ffmpeg lookup — `core/audio/tools.py`

`shutil.which` first, then **only** `/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`, `/usr/bin/ffmpeg`. No `C:\ffmpeg\bin`, no WinGet links. GUI Tools (merge/preprocess) inside Docker see Linux `/usr/bin/ffmpeg` in the image. Host `inbox-watch` uses its own `find_ffmpeg` (PATH only) — better for Windows **if** ffmpeg is on PATH; worse for Homebrew-not-on-PATH Macs (inbox-watch will miss Homebrew unless PATH includes it; the launchd plist injects `/opt/homebrew/bin`).

### Ollama URL — `resolve_ollama_base_url`

Rewrites `host.docker.internal` → `127.0.0.1` when **not** in a container (`/.dockerenv`). This is the right host-vs-container split for Mac **and** Windows Docker Desktop **and** a native Linux venv. Linux Compose on a real docker engine may need `extra_hosts: host.docker.internal:host-gateway` (not defined in `docker-compose.yml`); that is a Linux Docker networking issue, not inbox-watch.

### Corrections memory path

Darwin → `~/Library/Application Support/transcriptx/corrections.yml`; else XDG `~/.config/transcriptx/…`. Windows would get a fake XDG under `%USERPROFILE%\.config`, not `%APPDATA%`. Host-side only if native Python loads that module.

### Compose host glue

- `user: "${UID:-1000}:${GID:-1000}"` — bash `UID` is **not exported** by default, so Compose often interpolates **1000**. Accidental success when the Linux login is uid 1000. Other uids write `./data` as 1000. Windows has no `UID`; always 1000. Docker Desktop file ownership is already fictional on NTFS/virtiofs.
- `.env.example` `HOST_*` examples are `/Users/you/...`. Windows needs `C:\…` or WSL `/mnt/c/…` depending on where Compose runs.
- `NUMBA_CACHE_DIR=/tmp/numba_cache` documents virtiofs EIO on Docker Desktop — Mac/Windows host FS, not Linux overlay.

---

## H. Other host Python helpers

`audio_merge.py` / `audio_preprocess.py` / `workspace_backup.py` insert `src/` on `sys.path` and import `transcriptx`. They are as portable as the package + ffmpeg. ZIP backup uses stdlib; path separators inside archives are typically POSIX from `zipfile` — restore on Windows of a Mac-made ZIP is a general zip issue, not unique here.

They are **not** wired to inbox-watch. A Linux operator merging serial parts still uses Tools → Auto-merge (in the container, with image ffmpeg) or a native install.

---

## I. Findings (ranked)

**Design / honesty (not defects if the Mac-only story is the contract)**

1. **Audio inbox-watch is a whispermlx pipeline.** Linux and Windows cannot complete convert→STT→originals with supported tools. WhisperX remains a separate copy-paste recipe.
2. **No Linux/Windows service analogue** to the LaunchAgent. `--watch` is a terminal process; `--once` is cron-shaped with no unit files.
3. **Copyable commands are bash.** Matches Linux and macOS; not Windows PowerShell. WSL is the undocumented escape hatch.

**Defects if anyone runs these scripts on Windows (best-effort claim)**

4. **`find_admit_python` ignores `Scripts\python.exe`.** `--admit` fails unless `--admit-python` is set.
5. **Command generator extension check is case-sensitive** and strips only `/`. Wrong snippet for `file.MP3` / `C:\dir\`.
6. **Install/run docs** (`install`, `python3`, `~/.local/bin`, `.transcriptx/bin/python`) have no Windows stanza.
7. **Layout checks are case-sensitive** unlike `canonicalise_path`.

**Linux operational**

8. **G2 + Docker bind-mount inotify** can miss host drops (especially Docker Desktop). Polling host `inbox-watch` is the robust pattern — but STT is missing on Linux.
9. **Compose `${UID}`** often defaults to 1000. Document `export UID=$(id -u) GID=$(id -g)` or put them in `.env`.
10. **ffmpeg fallback paths** in Tools are Unix-only (host native GUI on Linux is OK via `/usr/bin`; Windows native GUI is not).

**Hygiene**

11. **`scripts/macos/*.plist` is a personal LaunchAgent** (absolute `/Users/89298/...`). Do not treat as a distribution artefact; it will confuse Linux/Windows readers who open `scripts/macos/`.
12. **CI never runs host scripts on Windows** (or macOS). `tests/scripts/test_inbox_watch.py` is stdlib-mockable and will pass on Ubuntu while `#4` stays latent.

---

## J. What would make Linux/Windows real

Small, local, still “best-effort Windows”:

- Discover `.transcriptx/Scripts/python.exe` and `.venv/Scripts/python.exe`; mention `py -3 scripts\inbox-watch.py` in `host-stt.md`.
- `command_gen`: `Path(input).suffix.lower()`; strip `/` and `\`; say “Git Bash / WSL / macOS / Linux shell”.
- Document Linux inbox-watch as **transcript copy + admit only**, or convert-without-STT, until a provider exists.
- Document Compose `UID`/`GID` on Linux; keep Windows on WSL2+Docker.

Larger (theme H / G follow-on):

- Decouple inbox-watch STT: `--transcribe {whispermlx-missing,whisperx-docker,none}`.
- `PollingObserver` fallback for G2 on bind mounts.
- systemd unit + a **templated** (not user-absolute) macOS plist; optional Windows Task Scheduler XML.
- `transcriptx.ps1` only if native Windows GUI is promoted off “best-effort”.

---

## K. Scope limits

Not reviewed as host daemons: Sphinx `make docs`, release `*.sh`, `count_sloc.py`, eval/bench scripts, workspaces frontend `copy-css.mjs`. Those are maintainer/Unix.

Not executed: Windows 11, WSL2, Debian/Fedora, exFAT USB, Defender-on-replace, Docker Desktop inotify on a watched inbox.

---

## Related

- [directory_watcher.md](../runtime/directory_watcher.md) — G2 vs host inbox-watch
- [host-stt.md](../runtime/host-stt.md) — whispermlx-missing / inbox-watch
- [install_verification_matrix.md](../runtime/install_verification_matrix.md) — OS cells
- [script_inventory_1_0.md](../dev/script_inventory_1_0.md) — platform column
- [architecture-review-2026-09-02.md](architecture-review-2026-09-02.md) — system model (host STT vs one analysis process)
