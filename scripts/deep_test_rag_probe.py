"""RAG-only deep-test probe: ingest + scoped search (no analysis pipeline)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List

from transcriptx.core.rag.api import RagAPI
from transcriptx.core.rag.embed import _normalize
from transcriptx.core.rag.settings import RagSettings
from transcriptx.core.segments import get_segments

DIM = 8


class FakeEmbedder:
    dim = DIM

    def embed_query(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for i, token in enumerate(text.lower().split()[:3]):
            vec[i % (self.dim - 1)] = 1.0
        vec[-1] = 0.01
        return _normalize(vec)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(t) for t in texts]


def run_probe(transcript_path: Path, label: str, tmp_root: Path) -> int:
    settings = RagSettings(
        data_dir=tmp_root / label,
        enabled=True,
        embed_model="fake-embed",
        embed_dim=DIM,
        ollama_base_url="http://example.invalid",
        chunk_chars=200,
        min_chunk_chars=8,
    )
    api = RagAPI(settings, embedder=FakeEmbedder())
    session_slug = f"probe_{label}"
    run_id = "run_probe"
    segments = get_segments(transcript_path, cache=True)
    api.ingest(
        transcript_path,
        session_slug,
        run_id,
        transcript_path.stem,
        segments,
    )
    hits = api.search("summary", session_slug=session_slug, run_id=run_id, k=3)
    status = api.index_status()
    print(
        label,
        "ok",
        f"segments={len(segments)}",
        f"hits={len(hits)}",
        f"index={status.get('status')}",
    )
    return 0 if hits else 1


def _probe_tmp_base() -> Path:
    raw = os.environ.get("TRANSCRIPTX_DEEP_TEST_RAG_TMP")
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "transcriptx_rag_probe"


def main(argv: list[str]) -> int:
    root = Path.cwd()
    tmp = _probe_tmp_base()
    tmp.mkdir(parents=True, exist_ok=True)
    paths = [
        ("mini", root / "tests/fixtures/mini_transcript.json"),
        ("large", root / "tests/fixtures/analysis_probes/large_norm.json"),
    ]
    if len(argv) > 1:
        paths = [("custom", Path(argv[1]))]
    rc = 0
    for label, path in paths:
        if not path.is_file():
            print(label, "skip", path, "missing")
            rc = 1
            continue
        rc |= run_probe(path, label, tmp)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
