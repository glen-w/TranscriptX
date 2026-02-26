# Plan: Default config save path in container (refined)

Refinements and gotchas incorporated for a bulletproof container story.

---

## Goal

Make the default config path inside the container point under the mounted volume (`/data`) so that saving config from the CLI persists across container runs. When `TRANSCRIPTX_CONFIG_DIR` is not set, behavior stays as today: config under project root (e.g. `<project>/.transcriptx/config.json`).

---

## 1. Import-time env read (gotcha)

`CONFIG_DIR = ...` is evaluated at **module import time**. That is fine for Docker (ENV is set before the process starts).

- Changing `TRANSCRIPTX_CONFIG_DIR` **after** import has no effect.
- **Tests:** Either set env vars **before** importing `persistence`, or keep monkeypatching `persistence.CONFIG_DIR` / `CONFIG_DRAFTS_DIR` (existing tests already do the latter).

No change for “runtime flexibility” (e.g. `get_config_dir()`) for this goal; import-time is acceptable.

---

## 2. Path handling: `.resolve()` and `expanduser()`

- `Path(env_value).resolve()` can behave differently by platform when the path does not exist. In Docker we set an absolute `/data/.transcriptx`, so it is safe.
- For “no surprises” and future `~` usage: use **`Path(env_value).expanduser()`** and **avoid `resolve()`** unless necessary (or document that we use it only when the value is an absolute path set by the image).

**Implementation:**  
`CONFIG_DIR = Path(os.getenv("TRANSCRIPTX_CONFIG_DIR")).expanduser()` when set; do not call `.resolve()` so non-existent paths are not normalized away. For Docker’s `/data/.transcriptx`, `expanduser()` is a no-op.

---

## 3. Directory creation before first write

- **Already satisfied:** `save_config_atomic()` in [src/transcriptx/core/config/persistence.py](src/transcriptx/core/config/persistence.py) does `target_path.parent.mkdir(parents=True, exist_ok=True)` (line 41). So the first save to `config.json` creates `CONFIG_DIR`, and the first save to a draft creates `CONFIG_DRAFTS_DIR`.
- No extra `CONFIG_DIR.mkdir(...)` at module level or at first use is required. If you ever add an entrypoint that touches config before any CLI run, you could create `/data/.transcriptx` there as well (see Permissions below).

---

## 4. Permissions and UID/GID (container)

On Linux, `./data:/data` can be owned by the host user while the container runs as another user (e.g. `transcriptx`), leading to “Permission denied” on config save.

**Mitigations:**

1. **Document:** In [docs/docker.md](docs/docker.md) (and optionally README), state: “Ensure the mounted `data/` (or the path you mount at `/data`) is **writable** by the container user.” Reference the existing “Permissions (Linux): root-owned outputs” section and the `user: "${UID}:${GID}"` option.
2. **Optional hardening:** In the Dockerfile, after `USER transcriptx` and before `ENTRYPOINT`, create the config dir so a fresh volume has the right ownership:
   - `RUN mkdir -p /data/.transcriptx /data/.transcriptx/drafts` and ensure `/data` is writable (e.g. `chown transcriptx:transcriptx /data` if the image owns `/data`). Note: when the user mounts a host dir over `/data`, the container-created dir is hidden; the important part is that the **mounted** dir is writable. So the primary mitigation is documentation; the RUN is optional for cases where `/data` is not mounted and the container writes there.

---

## 5. One config root and PROJECT_ROOT audit

- **Consistency:** `TRANSCRIPTX_CONFIG_DIR` is already used in [src/transcriptx/core/utils/config/main.py](src/transcriptx/core/utils/config/main.py) for the install-profile path. Using the same env in persistence keeps a single “config root” for the process.
- **Audit:** Confirm no other config-related paths are still anchored only to `PROJECT_ROOT` in a way that would surprise Docker users:
  - **persistence.py** – will use `TRANSCRIPTX_CONFIG_DIR` when set (this change).
  - **config/main.py** – already uses `TRANSCRIPTX_CONFIG_DIR` for install_profile.
  - **speaker_profiling.py** – `SPEAKER_DIR = PROJECT_ROOT / "transcriptx_data" / "speakers"` is separate (speaker files); not config. Could be a follow-up to align with `DATA_DIR` in Docker if desired.
  - **paths.py** – `DATA_DIR` already overridden by `TRANSCRIPTX_DATA_DIR`; config stays “next to project” unless `TRANSCRIPTX_CONFIG_DIR` is set.

**Decision:** Non-Docker default remains `<project>/.transcriptx`. Docker sets `TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx` so config is under the data volume by default; no change to default when env is unset.

---

## 6. Docs: explicit paths and override

In [docs/docker.md](docs/docker.md) (and optionally in [.env.example](.env.example)), state explicitly:

- **Default in container:** `/data/.transcriptx/config.json` (when image sets `TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx`).
- **Default outside container:** `<project>/.transcriptx/config.json` (when `TRANSCRIPTX_CONFIG_DIR` is unset).
- **Override:** `TRANSCRIPTX_CONFIG_DIR=/somewhere` → config at `/somewhere/config.json`, drafts at `/somewhere/drafts/`.

This avoids ambiguity and supports debugging.

---

## 7. Optional micro-test (follow-up)

A small unit test can guard against regressions:

- Set `TRANSCRIPTX_CONFIG_DIR` **before** importing `transcriptx.core.config.persistence` (or reload the module in the test), then assert `get_project_config_path()` is under that directory.
- If “set env before import” or module reload is awkward in the test harness, keep this as a follow-up.

---

## Implementation checklist

| Item | Action |
|------|--------|
| **persistence.py** | Add `import os`. Compute `CONFIG_DIR` from `os.getenv("TRANSCRIPTX_CONFIG_DIR")`: if set, `Path(env).expanduser()` (no `resolve()`); else `Path(PROJECT_ROOT) / ".transcriptx"`. Keep `CONFIG_DRAFTS_DIR = CONFIG_DIR / "drafts"`. |
| **Dockerfile** | Add `ENV TRANSCRIPTX_CONFIG_DIR=/data/.transcriptx` after `TRANSCRIPTX_DATA_DIR=/data`. Optionally add `RUN mkdir -p /data/.transcriptx /data/.transcriptx/drafts` and ownership if image owns `/data` (see §4). |
| **.env.example** | Document optional `TRANSCRIPTX_CONFIG_DIR`; note Docker sets it to `/data/.transcriptx`. |
| **docs/docker.md** | (1) Note that default config path in container is `/data/.transcriptx/config.json` and persists when `./data` is mounted at `/data`. (2) Add §6-style summary: default in container vs outside vs override. (3) In permissions section: “Ensure the mounted data/ is writable by the container user.” |
| **Tests** | No change required; existing monkeypatching of `CONFIG_DIR` / `CONFIG_DRAFTS_DIR` remains valid. Optional: add env-before-import test for `get_project_config_path()` (follow-up). |

---

## Summary

- **Import-time** config dir is acceptable; tests keep monkeypatching or set env before import.
- **Path:** use `expanduser()`, skip `resolve()` for env value.
- **Dirs:** already created in `save_config_atomic`; no extra mkdir required unless you add an entrypoint.
- **Permissions:** document writable mount; optionally create `/data/.transcriptx` in Dockerfile for non-mounted `/data` runs.
- **Consistency:** single env `TRANSCRIPTX_CONFIG_DIR`; quick audit of PROJECT_ROOT usages done; config default unchanged when env unset.
- **Docs:** explicit defaults (container / non-container / override) and permissions note.
- **Test:** optional env-before-import unit test as follow-up.
