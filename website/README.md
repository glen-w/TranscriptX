# TranscriptX website

Modest public landing (plain HTML/CSS, minimal JS for mobile nav).

- Open `index.html` locally, or deploy via GitHub Pages (`.github/workflows/pages.yml`).
- Public series badge should match [pyproject.toml](../pyproject.toml) `version` (currently **0.9.9.5**).
- Install snippet matches README: copy `.env.example` → `.env`, set `HOST_RECORDINGS_DIR`, then `docker compose up transcriptx-web`.
- Docs / Workflows / Compare CTAs point at the **Sphinx HTML guide** published beside this landing (`./guide/`), rebuilt from `docs/` on every qualifying `main` push.
- The sticky header nav is shared with `/guide/` via `website/chrome/` (Sphinx injects the same chrome so Workflows keeps Install / Docs / Workflows links).
- Full local preview (landing + guide): `pip install -e '.[docs]' && bash scripts/release/assemble_pages_site.sh` then open `_site/index.html`.
- Ko-fi support link in footer: https://ko-fi.com/C0C1XK8G
- Read the Docs remains the intended long-term hosted-docs host (see `docs/dev/rtd_go_live_checklist.md`); Pages `/guide/` keeps Sphinx content current until that go-live.
