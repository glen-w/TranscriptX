"""
HTML utilities for TranscriptX.

This module provides functions for generating HTML reports and visualizations
from transcript analysis results.
"""

import os
import re

from pathlib import Path
from typing import Any


def create_html_report(
    transcript_path: str,
    output_dir: str,
    analysis_results: dict[str, Any],
) -> str:
    """
    Create a comprehensive HTML report from analysis results.

    Args:
        transcript_path: Path to the original transcript file
        output_dir: Directory containing analysis results
        analysis_results: Dictionary containing analysis metadata

    Returns:
        Path to the generated HTML report
    """
    base_name = Path(transcript_path).stem
    report_path = os.path.join(output_dir, f"{base_name}_report.html")

    # Generate HTML content
    html_content = generate_html_content(base_name, analysis_results, output_dir)

    # Write HTML file
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return report_path


def generate_html_content(
    base_name: str, analysis_results: dict[str, Any], output_dir: str
) -> str:
    """
    Generate the HTML content for the report (Bootstrap 5, modular, extensible).
    """
    # Extract metadata
    analysis_results.get("modules_run", [])
    errors = analysis_results.get("errors", [])
    timestamp = analysis_results.get("timestamp", "Unknown")
    transcript_title = analysis_results.get("title", base_name)
    duration = analysis_results.get("duration", "N/A")
    num_speakers = analysis_results.get("num_speakers", "N/A")
    version = analysis_results.get("version", "1.0.0")
    speakers = analysis_results.get("speakers", [])
    summary_stats = analysis_results.get("summary_stats", {})
    transcript_segments = analysis_results.get("transcript_segments", [])
    entities = analysis_results.get("entities", [])
    key_moments = analysis_results.get("key_moments", [])
    interaction_data = analysis_results.get("interaction_network", {})
    module_data = analysis_results.get("module_data", {})
    toc_entries = []
    global_sections = []

    # Table of Contents (sticky)
    toc_entries.append(
        '<li class="list-group-item"><a href="#key-moments">Key Moments</a></li>'
    )
    toc_entries.append(
        '<li class="list-group-item"><a href="#dashboard">Summary Dashboard</a></li>'
    )
    toc_entries.append(
        '<li class="list-group-item"><a href="#transcript">Transcript</a></li>'
    )
    toc_entries += [
        '<li class="list-group-item"><a href="#global-wordclouds">Global Word Clouds</a></li>',
        '<li class="list-group-item"><a href="#interaction-networks">Interaction Networks</a></li>',
        '<li class="list-group-item"><a href="#readability">Readability</a></li>',
        '<li class="list-group-item"><a href="#downloads">Download Links</a></li>',
        '<li class="list-group-item"><a href="#all-modules">All Module Outputs</a></li>',
    ]

    # Summary Dashboard (quick stats, global charts)
    dashboard_html = f"""
    <section id="dashboard" class="mb-5">
      <div class="row g-4 align-items-center">
        <div class="col-md-8">
          <h1 class="display-5">{transcript_title}</h1>
          <div class="text-muted mb-2">Generated: {timestamp}</div>
          <div class="mb-2">Duration: <b>{duration}</b> &nbsp;|&nbsp; Speakers: <b>{num_speakers}</b></div>
        </div>
      </div>
      <div class="row mt-4">
        <div class="col">
          <div class="card shadow-sm">
            <div class="card-body">
              <h5 class="card-title">Quick Stats</h5>
              <div class="row row-cols-2 row-cols-md-4 g-2">
                <div class="col"><div class="stat-value">{summary_stats.get("total_words", "N/A")}</div><div class="stat-label">Total Words</div></div>
                <div class="col"><div class="stat-value">{summary_stats.get("segments", "N/A")}</div><div class="stat-label">Segments</div></div>
                <div class="col"><div class="stat-value">{summary_stats.get("avg_segment_length", "N/A")}</div><div class="stat-label">Avg. Segment Length</div></div>
                <div class="col"><div class="stat-value">{summary_stats.get("tic_rate", "N/A")}</div><div class="stat-label">Tic Rate</div></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- Placeholder for global charts (sentiment, emotion, etc.) -->
      <div class="row mt-4">
        <div class="col">
          <figure class="text-center">
            <img src="global_sentiment.png" alt="Global Sentiment Timeline" class="img-fluid" style="max-width:500px;">
            <figcaption>Global Sentiment Timeline</figcaption>
          </figure>
        </div>
        <div class="col">
          <figure class="text-center">
            <img src="global_emotion.png" alt="Global Emotion Timeline" class="img-fluid" style="max-width:500px;">
            <figcaption>Global Emotion Timeline</figcaption>
          </figure>
        </div>
      </div>
    </section>
    """

    # Global Analysis Sections
    global_sections.append(generate_global_wordclouds_section(output_dir))
    global_sections.append(generate_interaction_networks_section(output_dir))
    global_sections.append(generate_readability_section(output_dir))
    global_sections.append(generate_downloads_section(output_dir))

    # Key Moments Section
    key_moments_html = generate_key_moments_section(key_moments)
    # Transcript Section
    transcript_html = generate_transcript_section(
        transcript_segments, speakers, entities
    )
    # Interactive Network Section
    interactive_network_html = generate_interactive_network_section(interaction_data)
    # All Module Outputs Section
    all_modules_html = generate_all_modules_section(module_data, output_dir)

    # Error Section
    error_html = ""
    if errors:
        error_items = [f"<li>{e}</li>" for e in errors]
        error_html = f"""<section id="errors" class="alert alert-danger mt-4"><h2>Errors</h2><ul>{"".join(error_items)}</ul></section>"""

    # Footer
    footer_html = f"""
    <footer class="footer mt-5 py-3 bg-light border-top">
      <div class="container text-center">
        <span class="text-muted">Generated by TranscriptX v{version} &mdash; {timestamp}</span>
      </div>
    </footer>
    """

    # HTML Template
    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TranscriptX Report - {transcript_title}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://unpkg.com/cytoscape/dist/cytoscape.min.css" rel="stylesheet">
  <style>
    body {{ background: #f9f9f9; }}
    .container-xl {{ max-width: 1200px; margin: 0 auto; }}
    .sticky-toc {{ position: sticky; top: 1rem; z-index: 100; }}
    .stat-value {{ font-size: 1.5rem; font-weight: bold; color: #4f46e5; }}
    .stat-label {{ color: #666; font-size: 0.95rem; }}
    .speaker-accent {{ border-left: 6px solid var(--speaker-color, #4f46e5); }}
    .img-fluid {{ max-width: 500px; height: auto; }}
    .accordion-button:not(.collapsed) {{ background: #e9ecef; }}
    .table thead th {{ cursor: pointer; }}
    .sticky-toc .list-group-item a {{ color: #1976d2; text-decoration: none; }}
    .sticky-toc .list-group-item a:hover {{ text-decoration: underline; }}
    .transcript-segment.highlight {{ background: #fff3cd; }}
    #cy-network {{ width: 100%; height: 500px; border: 1px solid #ccc; border-radius: 8px; margin-bottom: 1rem; }}
    .search-highlight {{ background: #ffe066; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="container-xl py-4">
    <div class="row">
      <aside class="col-md-3 mb-4">
        <nav class="sticky-toc">
          <h5 class="mb-3">Table of Contents</h5>
          <ul class="list-group">
            {"".join(toc_entries)}
          </ul>
        </nav>
      </aside>
      <main class="col-md-9">
        {error_html}
        {key_moments_html}
        {dashboard_html}
        {transcript_html}
        {"".join(global_sections)}
        {interactive_network_html}
        {all_modules_html}
        {footer_html}
      </main>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>
  <script>
    // Sortable tables (Bootstrap Table + JS)
    document.querySelectorAll('table.sortable thead th').forEach(function(th) {{
      th.addEventListener('click', function() {{
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        Array.from(tbody.querySelectorAll('tr'))
          .sort(function(a, b) {{
            const i = Array.from(th.parentNode.children).indexOf(th);
            return a.children[i].textContent.localeCompare(b.children[i].textContent, undefined, {{numeric: true}});
          }} )
          .forEach(function(tr) {{ tbody.appendChild(tr); }} );
      }} );
    }} );
    // Transcript search and highlight
    document.getElementById('transcript-search').addEventListener('input', function() {{
      const query = this.value.toLowerCase();
      document.querySelectorAll('.transcript-segment').forEach(function(seg) {{
        const text = seg.textContent.toLowerCase();
        if (query && text.includes(query)) {{
          seg.classList.add('highlight');
        }} else {{
          seg.classList.remove('highlight');
        }}
        // Highlight keywords/entities
        seg.innerHTML = seg.innerHTML.replace(/<span class=\"search-highlight\">(.*?)<\\/span>/g, '$1');
        if (query) {{
          seg.innerHTML = seg.innerHTML.replace(new RegExp(query.replace(/[.*+?^${{}}()|[\\]\\]/g, '\\$&'), 'gi'), function(match) {{ return `<span class=\"search-highlight\">${{match}}</span>`; }} );
        }}
      }} );
    }} );
    // Cytoscape.js network
    if (window.cytoscape && document.getElementById('cy-network')) {{
      fetch('interaction_network.json').then(function(r) {{ return r.json(); }} ).then(function(data) {{
        const cy = cytoscape({{ container: document.getElementById('cy-network'), elements: data.elements, style: [
          {{ selector: 'node', style: {{ 'background-color': '#4f46e5', 'label': 'data(label)' }} }},
          {{ selector: 'edge', style: {{ 'width': 2, 'line-color': '#888', 'target-arrow-color': '#888', 'target-arrow-shape': 'triangle' }} }},
          {{ selector: ':selected', style: {{ 'background-color': '#ffe066', 'line-color': '#ffe066', 'target-arrow-color': '#ffe066' }} }},
        ], layout: {{ name: 'cose' }} }});
        cy.on('tap', 'node', function(evt) {{
          const node = evt.target;
          alert('Speaker: ' + node.data('label')); 
        }} );
      }} ).catch(function() {{
        document.getElementById('cy-network').outerHTML = '<div class="alert alert-warning">Interactive network unavailable. See static image above.</div>';
      }} );
    }}
  </script>
</body>
</html>
    """
    return html_template


# Modular section generators (stubs, to be expanded)
# def generate_speaker_section(speaker: dict, output_dir: str) -> str:
#     """Generate a per-speaker section with all required features."""
#     return ''


def generate_global_wordclouds_section(output_dir: str) -> str:
    return """<section id="global-wordclouds" class="mb-5"><h2>Global Word Clouds</h2><figure><img src="global_wordcloud.png" alt="Global Word Cloud" class="img-fluid"><figcaption>Global Word Cloud</figcaption></figure><a href="#dashboard" class="btn btn-link mt-3">Back to Top</a></section>"""


def generate_interaction_networks_section(output_dir: str) -> str:
    return """<section id="interaction-networks" class="mb-5"><h2>Interaction Networks</h2><figure><img src="interaction_network.png" alt="Interaction Network" class="img-fluid"><figcaption>Speaker Interaction Network</figcaption></figure><a href="#dashboard" class="btn btn-link mt-3">Back to Top</a></section>"""


def generate_readability_section(output_dir: str) -> str:
    return """<section id="readability" class="mb-5"><h2>Readability Scores</h2><table class="table table-striped sortable"><thead><tr><th>Metric</th><th>Score</th></tr></thead><tbody><tr><td>Flesch Reading Ease</td><td class="text-end">N/A</td></tr><tr><td>Gunning Fog Index</td><td class="text-end">N/A</td></tr></tbody></table><a href="#dashboard" class="btn btn-link mt-3">Back to Top</a></section>"""


def generate_downloads_section(output_dir: str) -> str:
    return """<section id="downloads" class="mb-5"><h2>Download Links</h2><ul><li><a href="data.csv">CSV Data</a></li><li><a href="data.json">JSON Data</a></li></ul><a href="#dashboard" class="btn btn-link mt-3">Back to Top</a></section>"""


# --- Country to Flag Emoji Utility ---
def country_to_flag_emoji(country: str) -> str:
    """
    Return the flag emoji for a given country name, or empty string if not found.
    Handles common country names and abbreviations.
    """
    if not country:
        return ""
    # Normalize country name
    c = country.strip().lower()
    # Common aliases
    aliases = {
        "us": "united states",
        "u.s.": "united states",
        "usa": "united states",
        "uk": "united kingdom",
        "uae": "united arab emirates",
        "south korea": "korea, republic of",
        "north korea": "korea, democratic people's republic of",
        "russia": "russian federation",
        "viet nam": "vietnam",
        "czech republic": "czechia",
        "ivory coast": "côte d'ivoire",
        "myanmar (burma)": "myanmar",
    }
    c = aliases.get(c, c)
    # ISO country code to flag emoji
    country_flags = {
        "afghanistan": "🇦🇫",
        "albania": "🇦🇱",
        "algeria": "🇩🇿",
        "andorra": "🇦🇩",
        "angola": "🇦🇴",
        "argentina": "🇦🇷",
        "armenia": "🇦🇲",
        "australia": "🇦🇺",
        "austria": "🇦🇹",
        "azerbaijan": "🇦🇿",
        "bahamas": "🇧🇸",
        "bahrain": "🇧🇭",
        "bangladesh": "🇧🇩",
        "barbados": "🇧🇧",
        "belarus": "🇧🇾",
        "belgium": "🇧🇪",
        "belize": "🇧🇿",
        "benin": "🇧🇯",
        "bhutan": "🇧🇹",
        "bolivia": "🇧🇴",
        "bosnia and herzegovina": "🇧🇦",
        "botswana": "🇧🇼",
        "brazil": "🇧🇷",
        "brunei": "🇧🇳",
        "bulgaria": "🇧🇬",
        "burkina faso": "🇧🇫",
        "burundi": "🇧🇮",
        "cambodia": "🇰🇭",
        "cameroon": "🇨🇲",
        "canada": "🇨🇦",
        "cape verde": "🇨🇻",
        "central african republic": "🇨🇫",
        "chad": "🇹🇩",
        "chile": "🇨🇱",
        "china": "🇨🇳",
        "colombia": "🇨🇴",
        "comoros": "🇰🇲",
        "congo": "🇨🇬",
        "congo, democratic republic of the": "🇨🇩",
        "costa rica": "🇨🇷",
        "croatia": "🇭🇷",
        "cuba": "🇨🇺",
        "cyprus": "🇨🇾",
        "czechia": "🇨🇿",
        "côte d'ivoire": "🇨🇮",
        "denmark": "🇩🇰",
        "djibouti": "🇩🇯",
        "dominica": "🇩🇲",
        "dominican republic": "🇩🇴",
        "ecuador": "🇪🇨",
        "egypt": "🇪🇬",
        "el salvador": "🇸🇻",
        "estonia": "🇪🇪",
        "eswatini": "🇸🇿",
        "ethiopia": "🇪🇹",
        "fiji": "🇫🇯",
        "finland": "🇫🇮",
        "france": "🇫🇷",
        "gabon": "🇬🇦",
        "gambia": "🇬🇲",
        "georgia": "🇬🇪",
        "germany": "🇩🇪",
        "ghana": "🇬🇭",
        "greece": "🇬🇷",
        "grenada": "🇬🇩",
        "guatemala": "🇬🇹",
        "guinea": "🇬🇳",
        "guinea-bissau": "🇬🇼",
        "guyana": "🇬🇾",
        "haiti": "🇭🇹",
        "honduras": "🇭🇳",
        "hungary": "🇭🇺",
        "iceland": "🇮🇸",
        "india": "🇮🇳",
        "indonesia": "🇮🇩",
        "iran": "🇮🇷",
        "iraq": "🇮🇶",
        "ireland": "🇮🇪",
        "israel": "🇮🇱",
        "italy": "🇮🇹",
        "jamaica": "🇯🇲",
        "japan": "🇯🇵",
        "jordan": "🇯🇴",
        "kazakhstan": "🇰🇿",
        "kenya": "🇰🇪",
        "kiribati": "🇰🇮",
        "korea, democratic people's republic of": "🇰🇵",
        "korea, republic of": "🇰🇷",
        "kuwait": "🇰🇼",
        "kyrgyzstan": "🇰🇬",
        "laos": "🇱🇦",
        "latvia": "🇱🇻",
        "lebanon": "🇱🇧",
        "lesotho": "🇱🇸",
        "liberia": "🇱🇷",
        "libya": "🇱🇾",
        "liechtenstein": "🇱🇮",
        "lithuania": "🇱🇹",
        "luxembourg": "🇱🇺",
        "madagascar": "🇲🇬",
        "malawi": "🇲🇼",
        "malaysia": "🇲🇾",
        "maldives": "🇲🇻",
        "mali": "🇲🇱",
        "malta": "🇲🇹",
        "marshall islands": "🇲🇭",
        "mauritania": "🇲🇷",
        "mauritius": "🇲🇺",
        "mexico": "🇲🇽",
        "micronesia": "🇫🇲",
        "moldova": "🇲🇩",
        "monaco": "🇲🇨",
        "mongolia": "🇲🇳",
        "montenegro": "🇲🇪",
        "morocco": "🇲🇦",
        "mozambique": "🇲🇿",
        "myanmar": "🇲🇲",
        "namibia": "🇳🇦",
        "nauru": "🇳🇷",
        "nepal": "🇳🇵",
        "netherlands": "🇳🇱",
        "new zealand": "🇳🇿",
        "nicaragua": "🇳🇮",
        "niger": "🇳🇪",
        "nigeria": "🇳🇬",
        "north macedonia": "🇲🇰",
        "norway": "🇳🇴",
        "oman": "🇴🇲",
        "pakistan": "🇵🇰",
        "palau": "🇵🇼",
        "palestine": "🇵🇸",
        "panama": "🇵🇦",
        "papua new guinea": "🇵🇬",
        "paraguay": "🇵🇾",
        "peru": "🇵🇪",
        "philippines": "🇵🇭",
        "poland": "🇵🇱",
        "portugal": "🇵🇹",
        "qatar": "🇶🇦",
        "romania": "🇷🇴",
        "russian federation": "🇷🇺",
        "rwanda": "🇷🇼",
        "saint kitts and nevis": "🇰🇳",
        "saint lucia": "🇱🇨",
        "saint vincent and the grenadines": "🇻🇨",
        "samoa": "🇼🇸",
        "san marino": "🇸🇲",
        "sao tome and principe": "🇸🇹",
        "saudi arabia": "🇸🇦",
        "senegal": "🇸🇳",
        "serbia": "🇷🇸",
        "seychelles": "🇸🇨",
        "sierra leone": "🇸🇱",
        "singapore": "🇸🇬",
        "slovakia": "🇸🇰",
        "slovenia": "🇸🇮",
        "solomon islands": "🇸🇧",
        "somalia": "🇸🇴",
        "south africa": "🇿🇦",
        "south sudan": "🇸🇸",
        "spain": "🇪🇸",
        "sri lanka": "🇱🇰",
        "sudan": "🇸🇩",
        "suriname": "🇸🇷",
        "sweden": "🇸🇪",
        "switzerland": "🇨🇭",
        "syria": "🇸🇾",
        "tajikistan": "🇹🇯",
        "tanzania": "🇹🇿",
        "thailand": "🇹🇭",
        "timor-leste": "🇹🇱",
        "togo": "🇹🇬",
        "tonga": "🇹🇴",
        "trinidad and tobago": "🇹🇹",
        "tunisia": "🇹🇳",
        "turkey": "🇹🇷",
        "turkmenistan": "🇹🇲",
        "tuvalu": "🇹🇻",
        "uganda": "🇺🇬",
        "ukraine": "🇺🇦",
        "united arab emirates": "🇦🇪",
        "united kingdom": "🇬🇧",
        "united states": "🇺🇸",
        "uruguay": "🇺🇾",
        "uzbekistan": "🇺🇿",
        "vanuatu": "🇻🇺",
        "venezuela": "🇻🇪",
        "vietnam": "🇻🇳",
        "yemen": "🇾🇪",
        "zambia": "🇿🇲",
        "zimbabwe": "🇿🇼",
    }
    # Try direct match
    flag = country_flags.get(c)
    if flag:
        return flag
    # Try title-case match
    flag = country_flags.get(c.title())
    if flag:
        return flag
    return ""


def wrap_tooltip_text(
    location: str, speaker: str, sentence: str, wrap_at: int = 20
) -> str:
    """
    Constructs a nicely wrapped HTML tooltip:
    - bold location name (with country flag emoji if available)
    - speaker name on new line
    - wrapped sentence (italics) after that
    """
    # Try to extract a country flag for the location name
    flag = country_to_flag_emoji(location)
    words = sentence.split()
    wrapped = []
    for i in range(0, len(words), wrap_at):
        wrapped.append(" ".join(words[i : i + wrap_at]))
    wrapped_text = "<br>".join(wrapped)
    if flag:
        return f"<b>{flag} {location}</b><br>{speaker}<br><i>{wrapped_text}</i>"
    return f"<b>{location}</b><br>{speaker}<br><i>{wrapped_text}</i>"


def generate_html_report(
    transcript_path: str,
    output_dir: str,
    analysis_results: dict[str, Any],
) -> str:
    """
    Generate a comprehensive HTML report from analysis results.

    This is a wrapper function that calls create_html_report for backward compatibility.

    Args:
        transcript_path: Path to the original transcript file
        output_dir: Directory containing analysis results
        analysis_results: Dictionary containing analysis metadata

    Returns:
        Path to the generated HTML report
    """
    return create_html_report(transcript_path, output_dir, analysis_results)


# --- Modular Section Generators ---
def generate_key_moments_section(key_moments: list) -> str:
    if not key_moments:
        return ""
    items = []
    for km in key_moments:
        anchor = f"transcript-segment-{km.get('segment_id', '')}"
        label = km.get("label", "Key Moment")
        score = km.get("score", "")
        summary = km.get("summary", "")
        items.append(
            f'<li><a href="#{anchor}"><b>{label}</b> ({score}): {summary}</a></li>'
        )
    return f"""<section id="key-moments" class="mb-5"><h2>Key Moments</h2><ul>{"".join(items)}</ul></section>"""


def generate_transcript_section(segments: list, speakers: list, entities: list) -> str:
    if not segments:
        return ""
    speaker_map = {s["id"]: s for s in speakers}
    {s["id"]: s.get("color", "#4f46e5") for s in speakers}

    def highlight_entities(text):
        if not entities:
            return text
        for ent in entities:
            pattern = re.compile(re.escape(ent["text"]), re.IGNORECASE)
            text = pattern.sub(
                f'<mark title="{ent.get("label", "Entity")}">{ent["text"]}</mark>',
                text,
            )
        return text

    transcript_html = [
        """<section id="transcript" class="mb-5"><h2>Transcript</h2><input id="transcript-search" class="form-control mb-3" placeholder="Search transcript..." type="text"><div class="accordion" id="transcriptAccordion">"""
    ]
    for i, seg in enumerate(segments):
        sid = seg.get("id", i)
        speaker_id = seg.get("speaker")
        speaker = speaker_map.get(speaker_id, {"name": speaker_id, "color": "#4f46e5"})
        color = speaker.get("color", "#4f46e5")
        name = speaker.get("name", speaker_id)
        ts = seg.get("start", "")
        text = highlight_entities(seg.get("text", ""))
        transcript_html.append(
            f"""
        <div class="accordion-item transcript-segment" id="transcript-segment-{sid}">
          <h2 class="accordion-header" id="heading-{sid}">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-{sid}" aria-expanded="false" aria-controls="collapse-{sid}">
              <span class="badge me-2" style="background:{color}">{name}</span>
              <span class="text-muted small">[{ts}]</span>
            </button>
          </h2>
          <div id="collapse-{sid}" class="accordion-collapse collapse" aria-labelledby="heading-{sid}" data-bs-parent="#transcriptAccordion">
            <div class="accordion-body">{text}</div>
          </div>
        </div>
        """
        )
    transcript_html.append("</div></section>")
    return "".join(transcript_html)


def generate_interactive_network_section(interaction_data: dict) -> str:
    # If interaction_data is empty, just show the static image
    return """<section id="interaction-networks" class="mb-5"><h2>Interaction Networks</h2><div id="cy-network"></div><figure><img src="interaction_network.png" alt="Interaction Network" class="img-fluid"><figcaption>Speaker Interaction Network (static fallback)</figcaption></figure><a href="#dashboard" class="btn btn-link mt-3">Back to Top</a></section>"""


def generate_all_modules_section(module_data: dict, output_dir: str) -> str:
    if not module_data:
        return ""
    html = ['<section id="all-modules" class="mb-5"><h2>All Module Outputs</h2>']
    for mod, data in module_data.items():
        html.append(f'<details class="mb-3"><summary><b>{mod.title()}</b></summary>')
        if isinstance(data, dict):
            for k, v in data.items():
                html.append(f"<div><b>{k}:</b> {v}</div>")
        elif isinstance(data, list):
            html.append("<ul>" + "".join(f"<li>{v}</li>" for v in data) + "</ul>")
        # Add images, CSV, JSON links if present
        mod_dir = os.path.join(output_dir, mod)
        if os.path.exists(mod_dir):
            for file in os.listdir(mod_dir):
                if file.endswith((".png", ".jpg", ".jpeg")):
                    html.append(
                        f'<figure><img src="{mod}/{file}" class="img-fluid"><figcaption>{file}</figcaption></figure>'
                    )
                elif file.endswith(".csv") or file.endswith(".json"):
                    html.append(f'<a href="{mod}/{file}" download>{file}</a>')
        html.append("</details>")
    html.append("</section>")
    return "".join(html)
