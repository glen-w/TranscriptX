"""Ensure Hugging Face checkpoints can load without torch>=2.6 torch.load.

Recent transformers refuse ``torch.load`` on older torch unless weights are
safetensors. Some Hub revisions still ship only ``pytorch_model.bin``. When the
local snapshot has a bin but no safetensors file, convert once with raw
``torch.load`` (allowed) and write ``model.safetensors`` beside it.

Callers must load via the returned local snapshot path: writing a file into the
Hub cache directory does not register it in Hub metadata, so repo-id loads still
ignore the converted weights.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from transcriptx.core.utils.downloads import downloads_disabled
from transcriptx.core.utils.logger import get_logger

log = get_logger()


def _local_snapshot_root(
    model_id: str, *, revision: Optional[str] = None
) -> Optional[Path]:
    """Resolve an already-cached snapshot dir without Hub network I/O."""
    try:
        from huggingface_hub import hf_hub_download, try_to_load_from_cache
    except Exception:
        return None

    for filename in ("pytorch_model.bin", "model.safetensors", "config.json"):
        try:
            cached = try_to_load_from_cache(
                repo_id=model_id, filename=filename, revision=revision
            )
        except Exception:
            cached = None
        if isinstance(cached, str):
            return Path(cached).parent
        # Non-string results (e.g. cached-no-exist markers) mean keep probing.

    if downloads_disabled():
        return None
    try:
        path = hf_hub_download(
            repo_id=model_id,
            filename="pytorch_model.bin",
            revision=revision,
            local_files_only=True,
        )
        return Path(path).parent
    except Exception:
        return None


def ensure_local_safetensors(
    model_id: str,
    *,
    revision: Optional[str] = None,
) -> Optional[Path]:
    """
    Ensure ``model.safetensors`` exists in a local snapshot.

    Returns the snapshot directory to pass to ``from_pretrained`` / ``pipeline``,
    or None when conversion is impossible.
    """
    root = _local_snapshot_root(model_id, revision=revision)
    if root is None:
        log.debug(
            "hf_safetensors: no local snapshot for %s@%s",
            model_id,
            revision or "default",
        )
        return None

    if (root / "model.safetensors").exists() or (
        root / "model.safetensors.index.json"
    ).exists():
        return root

    bin_path = root / "pytorch_model.bin"
    if not bin_path.exists():
        return None

    out_path = root / "model.safetensors"
    tmp_path = root / "model.safetensors.tmp"
    try:
        import torch
        from safetensors.torch import save_file

        # Bypass transformers' torch>=2.6 gate; torch itself can load the bin.
        load_kw = {"map_location": "cpu"}
        try:
            state = torch.load(bin_path, weights_only=True, **load_kw)
        except TypeError:
            state = torch.load(bin_path, **load_kw)
        if not isinstance(state, dict):
            return None
        tensors = {
            k: v.contiguous()
            for k, v in state.items()
            if hasattr(v, "contiguous") and hasattr(v, "dtype")
        }
        if not tensors:
            return None
        save_file(tensors, str(tmp_path))
        tmp_path.replace(out_path)
        log.info(
            "Converted %s pytorch_model.bin → model.safetensors for torch<2.6 load",
            model_id,
        )
        return root
    except Exception as e:
        log.warning(
            "hf_safetensors: failed converting %s: %s",
            model_id,
            e,
        )
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return None
