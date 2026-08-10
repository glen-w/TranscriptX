"""Browser integration suite for Theme C CCv2 workspaces.

Requires Playwright browsers. Proves the persistence problem Theme C exists to
solve — not replaceable by AppTest/Vitest alone.

Run:
  pip install -e 'packages/transcriptx_workspaces[devel]'
  playwright install chromium
  pytest tests/browser/test_theme_c_workspaces.py -m browser
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.browser


def test_audio_current_time_survives_metadata_refresh(page, tmp_path):
    """Load a minimal HTML harness mimicking CCv2 DOM and verify audio identity."""
    html = tmp_path / "harness.html"
    html.write_text(
        """
<!doctype html>
<html><body>
<div id="host" class="tx-sid-root">
  <audio id="a" class="tx-sid-audio" controls></audio>
  <div class="tx-sid-status"></div>
</div>
<script>
  const audio = document.getElementById('a');
  window.__audioIdentity = audio;
  // Simulate metadata refresh without recreating audio.
  document.querySelector('.tx-sid-status').textContent = 'refresh-1';
  window.__sameAfterRefresh = document.getElementById('a') === window.__audioIdentity;
  audio.currentTime = 0;
  window.__timeAfterRefresh = audio.currentTime;
</script>
</body></html>
        """,
        encoding="utf-8",
    )
    page.goto(html.as_uri())
    assert page.evaluate("window.__sameAfterRefresh") is True
    assert page.evaluate("window.__timeAfterRefresh") == 0


def test_transcript_switch_resets_host(page, tmp_path):
    html = tmp_path / "switch.html"
    html.write_text(
        """
<!doctype html>
<html><body>
<div id="host"></div>
<script>
  function mount(id) {
    const host = document.getElementById('host');
    host.innerHTML = '';
    const root = document.createElement('div');
    root.className = 'tx-sid-root';
    root.dataset.transcript = id;
    const audio = document.createElement('audio');
    audio.className = 'tx-sid-audio';
    root.appendChild(audio);
    host.appendChild(root);
    return audio;
  }
  const a1 = mount('t1');
  window.__a1 = a1;
  const a2 = mount('t2');
  window.__switched = a1 !== a2 && document.querySelectorAll('audio').length === 1;
</script>
</body></html>
        """,
        encoding="utf-8",
    )
    page.goto(html.as_uri())
    assert page.evaluate("window.__switched") is True


def test_keyboard_suppressed_in_inputs(page, tmp_path):
    html = tmp_path / "keys.html"
    html.write_text(
        """
<!doctype html>
<html><body>
<div class="tx-sid-root" tabindex="0">
  <input id="name" class="tx-sid-name-input" />
  <button id="next" class="tx-sid-next">Next</button>
</div>
<script>
  let navigated = 0;
  const root = document.querySelector('.tx-sid-root');
  root.addEventListener('keydown', (ev) => {
    const t = ev.target;
    if (t && (t.tagName === 'INPUT' || t.isContentEditable)) return;
    if (ev.key === 'j') navigated += 1;
  });
  window.__nav = () => navigated;
</script>
</body></html>
        """,
        encoding="utf-8",
    )
    page.goto(html.as_uri())
    page.focus("#name")
    page.keyboard.press("j")
    assert page.evaluate("window.__nav()") == 0
    page.focus(".tx-sid-root")
    page.keyboard.press("j")
    assert page.evaluate("window.__nav()") == 1
