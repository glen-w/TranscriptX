Type: ASSESSMENT
Authority: SECURITY.md

# TranscriptX security review (2026-08-23)

## 1. Executive verdict

TranscriptX has a credible local-first security baseline: Docker publishes to
loopback by default, the container runs without root privileges, transcript
imports and destructive library deletion have path-containment checks, workspace
restore defends against ZIP traversal, subprocesses use argument arrays rather
than shell interpolation, and sensitive transcription tokens are normally passed
through the environment.

The review nevertheless found **two high-priority path-containment defects**:

1. recording uploads trust the client-supplied filename and can write outside the
   recording imports directory; and
2. analysis profile names can traverse outside the profiles directory, enabling
   JSON file read, write, rename, or deletion under the process account.

Both defects are most serious if the Streamlit UI is exposed beyond loopback.
They remain worth fixing for defense in depth because filenames and imported
profile data are external input even in a local-first application.

The review also found unescaped dynamic HTML, unrestricted optional LLM
destinations, temporary-audio cleanup gaps, and supply-chain/deployment
hardening work. No evidence of embedded credentials, unsafe Python
deserialization, or `shell=True` execution was found in production code.

### Priority summary

| Priority | Count | Meaning |
|---|---:|---|
| P0 | 2 | Fix before recommending any shared or non-loopback deployment |
| P1 | 5 | Address before 1.0 or explicitly accept and document |
| P2 | 5 | Defense-in-depth, privacy, and release-process hardening |

## 2. Scope and method

This was a read-only static review of:

- `src/transcriptx/`, with emphasis on web input, filesystem operations,
  subprocesses, deserialization, generated HTML, outbound network calls,
  sensitive-data persistence, and destructive actions;
- Docker, Compose, native launcher, dependency manifests, and GitHub Actions;
- security, privacy, runtime, dependency-audit, and release documentation;
- tests that encode path-safety, archive-restore, cleanup, and secret-handling
  controls; and
- the current branch diff, reviewed separately for changed-code regressions.

The review did **not** include an authenticated penetration test, browser exploit
verification, dependency CVE scan of the built image, container image scan,
full-history secret scan, or network capture. Findings that require those checks
are labelled accordingly.

Severity is assessed against the documented trust model in
[`SECURITY.md`](../../SECURITY.md): one trusted machine user and a loopback-only
web bind. A non-loopback bind changes the threat model substantially because the
application has no authentication or per-action authorization.

## 3. Findings

### SR-01 — Profile names permit path traversal

**Priority:** P0  
**Severity:** High when the UI is reachable by an untrusted user; Medium under
the documented loopback trust model.  
**Evidence:** `src/transcriptx/core/utils/profile_manager.py:98-101`,
`:103-177`, `:210-231`, `:255-338`;
`src/transcriptx/web/page_modules/profiles.py:142-179`, `:253-267`.

`get_profile_path()` appends `f"{profile_name}.json"` without rejecting path
separators or `..`. Create and rename fields accept arbitrary trimmed text.
Consequently, a name such as `../../target` resolves outside the module profile
directory. The same helper feeds profile load, save, existence, delete, import,
and rename operations.

**Impact:** Read, overwrite, create, rename, or delete JSON files reachable by
the process account. The exact operation depends on the UI flow and whether the
target exists.

**Remediation:**

1. define one profile-name validator with a conservative character allowlist;
2. resolve every resulting path and require it to be a child of the expected
   module profile directory before any read or mutation;
3. reject symlinked module/profile paths where appropriate; and
4. add traversal tests for create, load, import, rename, and delete.

### SR-02 — Recording upload filename is not confined

**Priority:** P0  
**Severity:** High when the UI is reachable by an untrusted user; Medium under
the documented loopback trust model.  
**Evidence:** `src/transcriptx/web/services/recordings_service.py:91-113`.

`save_uploaded_file()` writes to
`RECORDINGS_IMPORTS_DIR / uploaded_file.name`. The filename comes from the upload
client and is neither reduced to a safe basename nor checked after path
resolution. A crafted upload protocol message containing path components can
escape the imports directory.

Transcript upload already provides a safer pattern in
`src/transcriptx/io/import_admission.py:127-147` and
`src/transcriptx/web/page_modules/upload_transcript.py:56-64`.

**Impact:** Arbitrary file write to locations writable by the application user,
including writable bind mounts.

**Remediation:** Reuse `sanitize_upload_basename()`, prefix the stored name with
a generated identifier, and enforce resolved-path containment immediately
before writing. Add tests for absolute paths, `..`, mixed separators, empty
names, collisions, and symlinked destinations.

### SR-03 — Non-loopback deployment exposes the full application without authentication

**Priority:** P1  
**Severity:** High if enabled; accepted/documented under the current local-only
product model.  
**Evidence:** `SECURITY.md:14-19`, `docker-compose.yml:86-95`,
`src/transcriptx/web/__main__.py:40-58`.

Compose safely publishes `127.0.0.1:8501` by default, but
`TRANSCRIPTX_BIND_HOST=0.0.0.0` exposes an unauthenticated interface containing
transcripts, generated artifacts, uploads, configuration operations, workspace
restore, and destructive cleanup.

**Remediation:** Keep loopback as the only supported default. For any shared
deployment, require an authenticated reverse proxy or VPN and document the
proxy's request-size and timeout controls. Consider a startup warning or an
explicit acknowledgement variable whenever the host bind is non-loopback.

### SR-04 — Profile import/export accepts arbitrary filesystem paths

**Priority:** P1  
**Severity:** Medium when the UI is reachable by an untrusted user; Low for a
trusted local operator.  
**Evidence:** `src/transcriptx/core/utils/profile_manager.py:233-294`,
`src/transcriptx/web/page_modules/profiles.py:288-327`.

The Profiles UI accepts raw import and export paths. Import reads any readable
JSON file; export copies over a user-selected path without a containment rule or
overwrite confirmation. This may be intentional power-user functionality, but
it becomes an arbitrary read/overwrite primitive outside the local trust model.

**Remediation:** Replace raw server paths with upload/download widgets where
possible. Otherwise confine operations to an explicit exchange directory,
confirm overwrite, and document that this surface is local-operator-only.

### SR-05 — Dynamic HTML is not consistently escaped

**Priority:** P1  
**Severity:** Medium for exported artifacts; Low-to-Medium for Streamlit
surfaces pending browser verification.  
**Evidence:** `src/transcriptx/utils/html_utils.py:86-105`, `:131-155`,
`:548-600`; `src/transcriptx/core/analysis/wordclouds/terms_io.py:72-82`,
`:102`, `:124-168`; `src/transcriptx/web/page_modules/run_analysis.py:628-667`;
`src/transcriptx/web/page_modules/charts.py:187-192`.

Legacy HTML reports interpolate transcript titles, error text, key moments,
entity text, and transcript segments into markup without HTML escaping. The
word-cloud explorer embeds unescaped titles, injects term values through
`innerHTML`, and embeds JSON without neutralizing `</script>`. Run Analysis and
chart metadata also pass dynamic values to `unsafe_allow_html=True`.

**Impact:** A crafted transcript, artifact manifest, or title may inject markup
and potentially script into an exported report or application-rendered HTML.
Exported files are the clearest executable context. Streamlit exploitability
must be confirmed against the shipped Streamlit renderer and browser policy.

**Remediation:** Escape text at the final output boundary; construct table cells
with `textContent`; encode embedded JSON so `</script>` cannot terminate the
script block; prefer existing escaped export helpers over the legacy generator;
and add hostile-string tests plus a browser check.

### SR-06 — Optional LLM destination permits arbitrary HTTP(S) hosts

**Priority:** P1  
**Severity:** Medium.  
**Evidence:** `src/transcriptx/core/llm/ollama_client.py:296-316`,
`:446-469`, `:615-635`; `docs/runtime/llm.md`.

LLM configuration validates only the URL scheme. When LLM features are enabled,
transcript excerpts and prompts can be sent to any configured HTTP(S) host. This
is documented for privacy, but there is no default host allowlist or block for
loopback-adjacent metadata/link-local destinations.

**Impact:** Transcript disclosure after misconfiguration and an SSRF primitive
if an attacker gains control of LLM configuration.

**Remediation:** Default to loopback and `host.docker.internal`; require an
explicit opt-in for remote hosts; block link-local/cloud metadata destinations;
and show a prominent data-egress warning for non-local endpoints.

### SR-07 — Temporary audio files survive preprocessing failures

**Priority:** P1  
**Severity:** Medium on a shared host; Low in the default single-user container.  
**Evidence:** `src/transcriptx/core/audio/preprocessing.py:347-375`,
`:430-468`.

Loudness normalization and denoising create `delete=False` WAV files and unlink
them only on the success path. Exceptions after export leave transcript-derived
audio in the system temporary directory.

**Remediation:** Initialize the temporary path outside the nested operation and
unlink it in `finally`, tolerating a missing file. Add failure-injection tests.

### SR-08 — Production dependency/image scanning is incomplete

**Priority:** P2  
**Severity:** Medium process risk.  
**Evidence:** `docs/dev/dependency_audit.md:6-17`,
`scripts/release/clean_env_audit.sh`, `scripts/release/image_pip_check.sh`,
`.github/workflows/ci.yml`.

Release CI runs `pip-audit` for the built wheel plus core dependencies, while
the fuller production image receives `pip check` but not a vulnerability scan.
The frontend lockfile also lacks a CI audit step. Therefore the release CVE
policy does not cover the complete shipped dependency surface.

**Remediation:** Audit the exact production image dependency freeze, add an
image scanner such as Trivy or Docker Scout, audit the frontend lockfile, retain
SBOM/reports as release evidence, and apply the documented waiver process to all
shipped components.

### SR-09 — Container build and runtime can be hardened further

**Priority:** P2  
**Severity:** Medium defense-in-depth gap.  
**Evidence:** `Dockerfile:7`, `:97`, `docker-compose.yml:17-95`.

The Python base image uses a floating tag rather than an immutable digest.
Compose runs as a non-root host UID, but does not set
`no-new-privileges`, capability drops, or a read-only root filesystem.

**Remediation:** Pin release builds by digest, add image provenance/SBOM
evidence, enable `no-new-privileges`, drop capabilities, and test a read-only
root filesystem with explicit writable mounts or `tmpfs`.

### SR-10 — Performance telemetry records full local paths by default

**Priority:** P2  
**Severity:** Low security / Medium privacy on shared storage.  
**Evidence:** `src/transcriptx/core/observability/perf.py:26-54`,
`:107-113`.

Streamlit performance instrumentation defaults on and normalizes file reads to
absolute paths in a JSONL file. The file is gitignored, but paths can disclose
usernames, project locations, and meeting names to other users with data-volume
access.

**Remediation:** Default instrumentation off outside development, record a
stable identifier or basename instead of an absolute path, and create the output
with owner-only permissions.

### SR-11 — Privacy-sensitive outbound and persistent features need deployment gates

**Priority:** P2  
**Severity:** Medium privacy risk; not a direct code-execution issue.  
**Evidence:** `src/transcriptx/utils/location_cache.py:36-55`,
`src/transcriptx/core/analysis/ner/__init__.py:290-291`,
`src/transcriptx/services/workspace_backup.py`,
`src/transcriptx/core/speaker_profiles/voice/privacy.py:30-67`.

NER geocoding can send transcript-derived location strings to Nominatim;
workspace backups are unencrypted ZIP files that may include transcripts,
recordings, corrections, and voice evidence; and voice matching stores
biometric-adjacent embeddings and clips. Voice matching has a fail-closed
consent mechanism and backup UI contains a PII warning, which are positive
controls.

**Remediation:** Provide a privacy/air-gap deployment profile that disables
geocoding and downloads, keep voice consent fail-closed, document backup
encryption and retention requirements, and inventory all egress in one operator
checklist.

### SR-12 — Automatic dependency installation should remain disabled in deployments

**Priority:** P2  
**Severity:** Low.  
**Evidence:** `src/transcriptx/core/utils/lazy_imports.py:76-107`,
`:170-191`.

Lazy imports can invoke `pip install` for missing optional packages unless core
or no-auto-install mode is active. The Docker path mitigates this, but native
deployments can still resolve mutable package indexes at runtime.

**Remediation:** Make no-auto-install the production default and install pinned,
audited dependencies only during build/setup.

## 4. Existing controls verified

- Default Compose host publication is loopback-only.
- Docker execution is non-root and does not mount the Docker socket.
- Transcript uploads sanitize logical basenames and use generated staging names.
- Folder import applies size limits and rejects symlinked inputs.
- Library deletion resolves paths and confines deletion to the managed
  transcript tree.
- Workspace restore verifies manifest hashes and rejects ZIP path traversal.
- Run cleanup validates output roots and rejects dangerous roots, symlinks, and
  overlaps.
- Production subprocess calls reviewed use argument arrays; no production
  `shell=True` path was identified.
- No `pickle.load`, unsafe YAML loader, or equivalent code-execution
  deserialization path was identified.
- Transcription presets reject secret-bearing fields; token redaction helpers
  exist; the normal Whisper MLX provider passes the Hugging Face token through
  the subprocess environment rather than the command line.
- LLM feedback storage rejects symlinks and uses owner-only modes.
- Streamlit usage statistics are disabled in Compose.
- The current branch diff tightens action capability filtering and preserves
  backend delete containment. The change-focused review found no Medium, High,
  or Critical regression.

## 5. Recommended remediation sequence

1. **P0:** Fix profile-name and recording-upload containment, with adversarial
   tests.
2. **P1:** Escape generated/dynamic HTML and add browser-level hostile-input
   verification.
3. **P1:** Make non-loopback operation an explicit authenticated deployment
   mode; restrict remote LLM endpoints.
4. **P1:** Guarantee temporary-audio cleanup and replace arbitrary profile
   import/export paths.
5. **P2:** Extend CVE scanning to the full image and frontend, pin the base image
   by digest, and harden container privileges.
6. **P2:** Ship a privacy/air-gap profile and minimize path-bearing telemetry.

## 6. Verification plan

The remediation should not be considered complete until these checks pass:

- adversarial unit tests for profile and recording path traversal, including
  symlink cases;
- generated-report tests containing `<`, `>`, quotes, `</script>`, and event
  handler payloads, followed by browser verification;
- `pip-audit` against the effective production Python freeze;
- container CVE scan and SBOM generation for the release image;
- frontend lockfile audit;
- full-history secret scan with a maintained scanner;
- Compose inspection for both default and non-loopback configurations; and
- a failure-injection test proving temporary WAV removal.

## 7. Review limitations

This assessment reports evidence visible in the repository on 2026-08-23.
Dependency vulnerability status changes continuously and must be established by
the release-time scans above. Browser behavior can also change with Streamlit
and browser versions, so the potential application-rendered XSS paths require
dynamic confirmation. No source-code remediation was performed as part of this
review.
