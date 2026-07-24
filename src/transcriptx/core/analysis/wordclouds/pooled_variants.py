"""
Selective pooled wordcloud variant inventory and classification (Phase 2 planning).

Each variant must have explicit pooled semantics before implementation; see project plan.
Values: safe_global | safe_per_speaker | unsafe_or_misleading | deferred
"""

from __future__ import annotations

from typing import Literal, TypedDict

Classification = Literal[
    "safe_for_pooled_global",
    "safe_for_pooled_per_speaker",
    "unsafe_or_misleading",
    "deferred",
]


class PooledVariantEntry(TypedDict):
    single_transcript_source: str
    pooled_global: Classification
    pooled_per_speaker: Classification
    notes: str


POOLED_WORDCLOUD_VARIANT_CLASSIFICATION: dict[str, PooledVariantEntry] = {
    "basic_frequency": {
        "single_transcript_source": "generate_wordcloud / run_all_wordclouds",
        "pooled_global": "safe_for_pooled_global",
        "pooled_per_speaker": "safe_for_pooled_per_speaker",
        "notes": "Phase 1: segments_concatenated_per_bucket; global join of buckets ordered.",
    },
    "tfidf_unigram": {
        "single_transcript_source": "generate_tfidf_wordclouds",
        "pooled_global": "safe_for_pooled_global",
        "pooled_per_speaker": "deferred",
        "notes": "Global pooled: one document per member transcript, mean TF-IDF; per-speaker pooled TF-IDF deferred until document model is fixed.",
    },
    "bigram_count": {
        "single_transcript_source": "generate_bigram_wordclouds / run_all global block",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Requires pooled global bigrams contract (ordered token stream across sessions).",
    },
    "tfidf_bigram": {
        "single_transcript_source": "generate_bigram_tfidf_wordclouds",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Same document-model discipline as TF-IDF unigram.",
    },
    "verbal_tics": {
        "single_transcript_source": "generate_tic_wordclouds",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Likely safe once input basis is defined; not yet implemented for group.",
    },
    "pos_filtered": {
        "single_transcript_source": "generate_pos_wordclouds",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Pool text then same nlp path; explicit basis required.",
    },
    "keyphrase_noun_chunks": {
        "single_transcript_source": "emit_keyphrase_wordclouds",
        "pooled_global": "safe_for_pooled_global",
        "pooled_per_speaker": "deferred",
        "notes": (
            "Pool pre-ranked noun_chunk rows by canonical_key "
            "(keyphrase_noun_chunk_pool); never concat-reparse. "
            "Weights from group aggregate rank_weight."
        ),
    },
    "keyphrase_yake": {
        "single_transcript_source": "emit_keyphrase_wordclouds",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Deferred until document model for YAKE across sessions is fixed.",
    },
    "keyphrase_keybert": {
        "single_transcript_source": "emit_keyphrase_wordclouds",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Deferred until document model for KeyBERT across sessions is fixed.",
    },
    "terms_json_and_explorer": {
        "single_transcript_source": "_save_terms_json / _save_wordcloud_view",
        "pooled_global": "deferred",
        "pooled_per_speaker": "deferred",
        "notes": "Selective parity: not automatic with chart image; image-only must be explicit in metadata.",
    },
}
