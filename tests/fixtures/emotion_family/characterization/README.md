# Emotion-family characterization fixtures

Generated only from committed deterministic test doubles
(`tests/unit/emotion_family_char/harness.py`). Never copy live Hugging Face
or NRC runtime output.

Refresh::

    UPDATE_EMOTION_FAMILY_CHARACTERIZATION=1 pytest \
      tests/unit/test_emotion_family_characterization.py -q

Lexical cache asymmetry (documented, not fixed in extract wave):
`needed_sids` includes every non-empty segment, but unsupported-language
rows are not stored — mixed-language transcripts may never inference-cache-hit.
