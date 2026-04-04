"""Term payloads, JSON terms artifacts, and wordcloud explorer HTML."""

from __future__ import annotations

import json
from typing import Any

from transcriptx.core.analysis.wordclouds.models import WordcloudTerm, WordcloudTerms
from transcriptx.core.analysis.wordclouds.output_bridge import _active_output_service


def _build_terms_payload(
    freq: dict[str, Any],
    *,
    variant: str,
    variant_key: str,
    speaker: str | None,
    ngram: int,
    metric: str,
    min_count: int | None = None,
    min_bigram_count: int | None = None,
    output_service: Any | None = None,
) -> dict[str, Any]:
    sorted_items = sorted(freq.items(), key=lambda item: item[1], reverse=True)
    terms = [
        WordcloudTerm(term=term, value=float(value), rank=idx + 1)
        for idx, (term, value) in enumerate(sorted_items)
    ]
    svc = _active_output_service(output_service)
    run_id = svc.run_id if svc else None
    transcript_key = svc.base_name if svc else None
    payload = WordcloudTerms(
        source="wordclouds",
        variant=variant,
        variant_key=variant_key,
        speaker=speaker,
        ngram=ngram,
        metric=metric,
        terms=terms,
        min_count=min_count,
        min_bigram_count=min_bigram_count,
        run_id=run_id,
        transcript_key=transcript_key,
    )
    return payload.to_dict()


def _save_terms_json(
    payload: dict[str, Any],
    *,
    filename: str,
    speaker: str | None,
    output_service: Any | None = None,
) -> str | None:
    svc = _active_output_service(output_service)
    if not svc:
        return None
    if speaker:
        safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
        name = f"{safe_speaker}_{filename}.terms"
        return svc.save_data(
            payload,
            name,
            format_type="json",
            subdirectory="speakers",
            speaker=speaker,
        )
    name = f"{filename}.terms"
    return svc.save_data(payload, name, format_type="json")


def _build_wordcloud_explorer_html(title: str, payload: dict[str, Any]) -> str:
    terms_json = json.dumps(payload)
    wc_cdn = "https://cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.js"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <script src="{wc_cdn}"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 16px; }}
    .controls {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }}
    .controls label {{ font-size: 12px; color: #333; }}
    #cloudWrap {{ width: 100%; height: 480px; position: relative; }}
    #wordcloudCanvas {{ display: block; width: 100%; height: 100%; }}
    #wordcloudEmptyState {{
      position: absolute; inset: 0; display: flex; align-items: center;
      justify-content: center; text-align: center; padding: 16px;
      color: #555; font-size: 14px; background: #fafafa; border: 1px solid #e0e0e0;
      box-sizing: border-box;
    }}
    #wordcloudEmptyState[hidden] {{ display: none !important; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 12px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    .actions {{ display: flex; gap: 8px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <div class="controls">
    <label>Search<br><input id="search" type="text" placeholder="filter terms"></label>
    <label>Top N<br><input id="topN" type="number" value="50" min="1" max="500"></label>
    <label>Min Value<br><input id="minValue" type="number" value="0" step="0.01"></label>
    <label>Sort<br>
      <select id="sortMode">
        <option value="value">Value</option>
        <option value="term">Term</option>
        <option value="rank">Rank</option>
      </select>
    </label>
    <div class="actions">
      <button id="copyTerms">Copy filtered terms</button>
      <button id="downloadCsv">Download CSV</button>
    </div>
  </div>
  <div id="cloudWrap">
    <canvas id="wordcloudCanvas" width="800" height="480" aria-label="Word cloud"></canvas>
    <div id="wordcloudEmptyState" data-wordcloud-empty="1" hidden>No terms match the current filters.</div>
  </div>
  <div id="table"></div>
  <script>
    window.WORDCLOUD_TERMS = {terms_json};
  </script>
  <script>
    const MAX_CLOUD_WORDS = 120;
    const MIN_FONT_CSS = 14;
    const MAX_FONT_CSS = 72;
    /* Larger grid reduces overlap on dense transcripts (wordcloud min grid is 4). */
    const GRID_SIZE = 14;

    const terms = window.WORDCLOUD_TERMS.terms || [];
    const searchInput = document.getElementById('search');
    const topNInput = document.getElementById('topN');
    const minValueInput = document.getElementById('minValue');
    const sortModeInput = document.getElementById('sortMode');
    const tableContainer = document.getElementById('table');
    const cloudWrap = document.getElementById('cloudWrap');
    const canvas = document.getElementById('wordcloudCanvas');
    const emptyState = document.getElementById('wordcloudEmptyState');

    let resizeTimer = null;

    function filteredTerms() {{
      const search = searchInput.value.toLowerCase();
      const minValue = parseFloat(minValueInput.value || '0');
      const topN = parseInt(topNInput.value || '50', 10);
      let items = terms.filter(t => t.term.toLowerCase().includes(search) && t.value >= minValue);
      const sortMode = sortModeInput.value;
      if (sortMode === 'term') {{
        items = items.sort((a, b) => a.term.localeCompare(b.term));
      }} else if (sortMode === 'rank') {{
        items = items.sort((a, b) => a.rank - b.rank);
      }} else {{
        items = items.sort((a, b) => b.value - a.value);
      }}
      return items.slice(0, topN);
    }}

    function renderTable(items) {{
      const rows = items.map(t => `<tr><td>${{t.rank}}</td><td>${{t.term}}</td><td>${{t.value}}</td></tr>`).join('');
      tableContainer.innerHTML = `
        <table>
          <thead><tr><th>Rank</th><th>Term</th><th>Value</th></tr></thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}

    function syncCanvasToLayout() {{
      const dpr = window.devicePixelRatio || 1;
      const rect = cloudWrap.getBoundingClientRect();
      const cssW = Math.max(1, Math.floor(rect.width));
      const cssH = Math.max(1, Math.floor(rect.height));
      canvas.style.width = cssW + 'px';
      canvas.style.height = cssH + 'px';
      canvas.width = Math.max(1, Math.round(cssW * dpr));
      canvas.height = Math.max(1, Math.round(cssH * dpr));
      return dpr;
    }}

    function clearCloudCanvas() {{
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }}

    function buildCloudList(items) {{
      const cap = Math.min(items.length, MAX_CLOUD_WORDS);
      const slice = items.slice(0, cap);
      /* sqrt dampens extreme counts for font sizing */
      const scaled = slice.map(t => Math.sqrt(Math.max(Number(t.value), 0)));
      if (scaled.length === 0) return [];
      const minS = Math.min.apply(null, scaled);
      const maxS = Math.max.apply(null, scaled);
      let norm;
      if (minS === maxS) {{
        norm = scaled.map(() => 0.5);
      }} else {{
        norm = scaled.map(s => (s - minS) / (maxS - minS));
      }}
      return slice.map((t, i) => [t.term, norm[i]]);
    }}

    function renderCloud(items) {{
      const dpr = syncCanvasToLayout();
      if (items.length === 0) {{
        return;
      }}
      const list = buildCloudList(items);
      if (list.length === 0) {{
        clearCloudCanvas();
        return;
      }}
      try {{
        WordCloud.stop();
      }} catch (e) {{}}

      const weightToPx = function (w) {{
        return (MIN_FONT_CSS + w * (MAX_FONT_CSS - MIN_FONT_CSS)) * dpr;
      }};

      WordCloud(canvas, {{
        list: list,
        gridSize: GRID_SIZE,
        weightFactor: weightToPx,
        minRotation: 0,
        maxRotation: 0,
        rotateRatio: 0,
        shuffle: false,
        backgroundColor: '#fff',
        color: 'random-dark',
        clearCanvas: true,
        drawOutOfBound: false
      }});
    }}

    function render() {{
      const items = filteredTerms();
      renderTable(items);
      if (items.length === 0) {{
        emptyState.removeAttribute('hidden');
        emptyState.textContent = 'No terms match the current filters.';
        syncCanvasToLayout();
        clearCloudCanvas();
        return;
      }}
      if (typeof WordCloud === 'undefined') {{
        emptyState.removeAttribute('hidden');
        emptyState.textContent = 'Word cloud library failed to load. Check your network connection.';
        syncCanvasToLayout();
        clearCloudCanvas();
        return;
      }}
      emptyState.setAttribute('hidden', '');
      renderCloud(items);
    }}

    function scheduleRender() {{
      if (resizeTimer) window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(function () {{
        resizeTimer = null;
        render();
      }}, 150);
    }}

    function toCsv(items) {{
      const rows = ['term,value'].concat(items.map(t => `${{t.term}},${{t.value}}`));
      return rows.join('\\n');
    }}

    document.getElementById('copyTerms').addEventListener('click', () => {{
      const items = filteredTerms();
      const csv = toCsv(items);
      navigator.clipboard.writeText(csv);
    }});

    document.getElementById('downloadCsv').addEventListener('click', () => {{
      const items = filteredTerms();
      const csv = toCsv(items);
      const blob = new Blob([csv], {{ type: 'text/csv' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'wordcloud_terms.csv';
      a.click();
      URL.revokeObjectURL(url);
    }});

    searchInput.addEventListener('input', render);
    topNInput.addEventListener('input', render);
    minValueInput.addEventListener('input', render);
    sortModeInput.addEventListener('change', render);
    window.addEventListener('resize', scheduleRender);
    if (typeof ResizeObserver !== 'undefined') {{
      const ro = new ResizeObserver(scheduleRender);
      ro.observe(cloudWrap);
    }}
    render();
  </script>
</body>
</html>"""
