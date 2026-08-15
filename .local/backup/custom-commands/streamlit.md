# Restart Streamlit app (# streamlit)

Kill any Streamlit process on port 8501 and start the full TranscriptX app with Speaker Studio enabled.
Execute from the workspace root.

---

## 1. Kill existing Streamlit

- Find the process using port 8501 (e.g. `lsof -i :8501` or `lsof -ti :8501`).
- Kill that process (e.g. `kill $(lsof -ti :8501)` or the PID from lsof).
- Confirm the port is free (e.g. `lsof -i :8501` returns nothing).

---

## 2. Start the full app

- Run in the background:
  ```bash
  TRANSCRIPTX_ENABLE_SPEAKER_STUDIO=1 streamlit run src/transcriptx/web/app.py --server.headless true --server.port 8501
  ```
- This starts the full app (Overview, Charts, Data, Explorer, Groups, Statistics, Search, Speaker Studio, Insights, Configuration, etc.) with Speaker Studio enabled.

---

## 3. Verify

- Optionally check that the app is up: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8501/` (expect 200).
- Report that the app is running at **http://127.0.0.1:8501/** with Speaker Studio on.

---

## Execution rules

- Run from the workspace root.
- Do not start a second Streamlit instance on 8501 if one is already running; kill the existing one first.
