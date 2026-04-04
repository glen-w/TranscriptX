# Export Exemplars (# export-exemplars)

Find the 10 most representative files in the workspace about a given topic and copy them (flat, no subfolders) into a new folder on the Desktop named after the topic.

**Usage:** `/export-exemplars <topic>`
Example: `export-exemplars docker setup` → finds 10 files best showing Docker setup and copies them to `~/Desktop/docker setup/`.

Execute from the workspace root. The topic is everything after "export-exemplars" in the user's message.

---

## 1. Parse the topic

- Take the full topic phrase from the user (e.g. "docker setup", "authentication", "API rate limiting").
- The destination folder name is exactly this topic (with spaces allowed): `~/Desktop/<topic>/`.
- Normalize for filesystem: create the folder with the topic as given; avoid characters that are invalid in folder names.

---

## 2. Find representative files

- Use **semantic search** (and optionally grep for filenames) to find files that best illustrate the topic.
- Run multiple targeted searches if needed (e.g. "Where is Docker configured?" "How is the Docker image built?" "docker-compose setup") to get good coverage.
- From the combined results, **choose the 10 most representative files**:
  - Prefer files that directly implement or document the topic over tangentially related ones.
  - Prefer a mix of code, config, and docs if relevant (e.g. Dockerfile, docker-compose.yml, README section).
  - Exclude binary files, very large generated files, and lockfiles (e.g. package-lock.json, poetry.lock) unless they are central to the topic.
- If fewer than 10 clearly relevant files exist, copy only those; do not pad with unrelated files.

---

## 3. Copy to Desktop (flat layout)

- Create the folder: `~/Desktop/<topic>/` (e.g. `~/Desktop/docker setup/`).
- Copy each of the 10 (or fewer) files into this folder **without** preserving subfolder structure.
- **Filenames:** use the file's basename (e.g. `Dockerfile`, `docker-compose.yml`). If two files have the same basename, disambiguate (e.g. `README.md` and `README-docs.md`, or `config-1.yaml` and `config-2.yaml`) so nothing is overwritten.
- Use `cp` (or equivalent) to copy; do not move or delete originals.
- If the destination folder already exists, add files into it and disambiguate names if needed; do not delete existing contents unless the user asked to replace.

---

## 4. Summarize

- List the 10 (or fewer) files that were copied and their original paths.
- Give the user the path to the new folder: `~/Desktop/<topic>/`.

---

## Execution rules

- Only copy; never delete or modify the originals.
- Resolve the Desktop path appropriately (e.g. `$HOME/Desktop` or `~/Desktop` on macOS).
- If the topic is empty or missing, ask the user to specify the topic.
