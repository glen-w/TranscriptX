"""Concern-scoped support helpers for LLM-backed analysis modules.

This package intentionally has no re-exports: import from the concrete
submodules (``hashing``, ``json_parse``, ``prompts``, ``provenance``,
``artifacts``, ``speakers``, ``filenames``, ``narrative_source``,
``narrative_contract``, ``action_items_contract``, ``action_items_render``,
``runtime``, ``text_cleanup``). Keeping this ``__init__`` empty prevents the
package from becoming a new kitchen-sink facade.
"""
