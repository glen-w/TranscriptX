# transcriptx-workspaces

Streamlit Components v2 package for TranscriptX Theme C high-interaction
workspaces: Speaker Identification, Corrections Studio review, and Transcript
Correct-mode word selection.

Install with the GUI extra from a git checkout:

```bash
pip install -e ".[web]"
```

or:

```bash
pip install -e packages/transcriptx_workspaces
```

Corrections review rolls back to Streamlit widgets with
`TX_CORRECTIONS_WORKSPACE_COMPONENT=0`. Speaker ID has no classic widget
fallback — missing this package is an install error.

## Build

```bash
cd packages/transcriptx_workspaces/transcriptx_workspaces/frontend
npm ci
npm run build
```

Built assets under `frontend/build/` are committed so installs do not require
Node at runtime. CI rebuilds hashed `speaker_id-*`, `corrections-*`, and
`viewer_edit-*` bundles.

Registered component keys:

- `transcriptx-workspaces.speaker_id_workspace`
- `transcriptx-workspaces.corrections_workspace`
- `transcriptx-workspaces.viewer_edit_workspace`
