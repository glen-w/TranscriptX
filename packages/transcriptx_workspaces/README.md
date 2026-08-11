# transcriptx-workspaces

Streamlit Components v2 package for TranscriptX Theme C high-interaction
workspaces. Scaffolded from Streamlit's official `component-template` v2
(template-reactless), then specialised for Speaker Identification.

The Speaker ID workspace feature flag is **default-on**. Roll back with
`TX_SPEAKER_ID_WORKSPACE_COMPONENT=0` (see `docs/dev/theme_c_workspaces_ccv2.md`).
If this package is not installed, Speaker ID falls through to the classic UI.

## Build

```bash
cd packages/transcriptx_workspaces/transcriptx_workspaces/frontend
npm ci
npm run build
```

Built assets under `frontend/build/` are committed so installs do not require
Node at runtime. CI rebuilds and fails on drift.

## Install

```bash
pip install -e packages/transcriptx_workspaces
```

Registered component key: `transcriptx-workspaces.speaker_id_workspace`
