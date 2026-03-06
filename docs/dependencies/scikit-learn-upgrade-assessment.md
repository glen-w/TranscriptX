# Scikit-learn upgrade assessment (1.3 → ≥1.6 for BERTopic)

**Status:** BERTopic is currently unwired. This assessment applies only if the feature is re-enabled.

**Context:** BERTopic and its stack (hdbscan, umap-learn) require `sklearn.utils.validation.validate_data`, which exists only in scikit-learn 1.6+. We added `scikit-learn>=1.6` to the `bertopic` extra and to the auto-install fallback so BERTopic works. This document assesses impact on the rest of the codebase.

## Summary

- **Upgrade scope:** Only when the BERTopic extra is installed or when auto-install runs for bertopic. Base `requirements.txt` still pins `scikit-learn==1.3.0` for non-BERTopic installs.
- **Conclusion:** Low risk. Our code uses only stable public sklearn APIs; numpy is already above sklearn 1.6’s minimum; no deprecated/internal APIs in use. Upgrading to ≥1.6 when using BERTopic is recommended.

## In-repo sklearn usage

| Location | APIs used |
|----------|-----------|
| `core/analysis/topic_modeling/utils.py` | NMF, LatentDirichletAllocation, CountVectorizer, TfidfVectorizer, silhouette_score, train_test_split |
| `core/analysis/topic_modeling/lda.py` | LatentDirichletAllocation, CountVectorizer |
| `core/analysis/topic_modeling/nmf.py` | NMF, TfidfVectorizer |
| `core/analysis/wordclouds/analysis.py` | TfidfVectorizer |
| `core/analysis/acts/ml_classifier.py` | RandomForestClassifier, TfidfVectorizer |
| `core/analysis/semantic_similarity/clustering.py` | TfidfVectorizer, DBSCAN |
| `core/analysis/semantic_similarity/similarity.py` | TfidfVectorizer, cosine_similarity |
| `core/analysis/exemplars.py` | TfidfVectorizer |
| `core/analysis/dynamics/momentum.py` | ENGLISH_STOP_WORDS |
| `core/utils/similarity_utils.py` | TfidfVectorizer, cosine_similarity |
| `core/utils/speaker_profiling.py` | TfidfVectorizer |
| `database/speaker_profiling.py` | TfidfVectorizer |
| `database/vocabulary_storage.py` | TfidfVectorizer |

All of these are stable public APIs with no breaking changes between 1.3 and 1.6 for our usage. We do **not** use: `set_output`, `_validate_data`, `check_array`, or other internals that changed.

## NumPy

- **scikit-learn 1.3:** numpy >= 1.17.3  
- **scikit-learn 1.6:** numpy >= 1.19.5  
- **Current pin (requirements.txt):** numpy == 1.26.4  

So numpy is already above both minimums; upgrading sklearn does not require a numpy upgrade and should not introduce new numpy-related breakage.

## Other dependencies

- No other project dependencies were found that pin a maximum scikit-learn or numpy version that would conflict with sklearn 1.6 and numpy 1.26.4.
- Optional stacks (spacy, sentence-transformers, pyannote, etc.) are not known to require sklearn < 1.6; they typically rely on numpy/sklearn in compatible ranges.

## Security note

scikit-learn 1.3 is affected by CVE-2024-5206 (TfidfVectorizer `stop_words_` data leakage); the fix is in 1.5.0+. Using 1.6+ when BERTopic is installed improves security for TfidfVectorizer usage across the app in that environment.

## BERTopic stack: transformers and sentence-transformers

The BERTopic extra also pulls in:

- **sentence-transformers>=3.0** — Uses `hf_hub_download` (new huggingface_hub). Version 5.x requires `transformers>=4.41` (e.g. `is_torch_npu_available`).
- **transformers>=4.41** — Required so sentence-transformers 3+/5+ import correctly. Base `requirements.txt` pins `transformers<4.32.0` (emotion / spacy-transformers). Installing the bertopic extra or using auto-install may therefore **upgrade transformers** to ≥4.41 in that environment, which can affect the emotion stack or other code that assumes `<4.32`. If both BERTopic and emotion are needed, use a dedicated venv for one stack or accept testing under the upgraded transformers.

## Recommendation

- Keep `scikit-learn>=1.6` and `transformers>=4.41`, `sentence-transformers>=3.0` in the `bertopic` extra and in the auto-install fallback.
- Leave `requirements.txt` as-is for installs that do not use BERTopic.
- If you see any sklearn-related regressions after upgrading in a BERTopic environment, they are likely from a dependency (e.g. hdbscan/umap) rather than from our own code; we can then pin `scikit-learn` to a narrow range (e.g. `>=1.6,<1.7`) if needed.

Last assessed: 2026-02-08.
