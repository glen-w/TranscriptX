"""Ensure Hugging Face checkpoints can load without torch>=2.6 torch.load.

Recent transformers refuse ``torch.load`` on older torch unless weights are
safetensors. Some Hub revisions still ship only ``pytorch_model.bin``. When the
local snapshot has a bin but no safetensors file, convert once with raw
``torch.load`` (allowed) and write ``model.safetensors`` beside it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from transcriptx.core.utils.downloads import downloads_disabled
from transcriptx.core.utils.logger import get_logger

log = get_logger()


def ensure_local_safetensors(
    model_id: str,
    *,
    revision: Optional[str] = None,
) -> bool:
    """
    Return True if safetensors weights are available locally after this call.

    No-op when safetensors already exist. Returns False when conversion is
    impossible (no local snapshot / no pytorch_model.bin / conversion error).
    """
    try:
        from huggingface_hub import snapshot_download
    except Exception:
        return False

    local_only = bool(downloads_disabled())
    try:
        root = Path(
            snapshot_download(
                repo_id=model_id,
                revision=revision,
                local_files_only=local_only,
            )
        )
    except Exception as e:
        log.debug(
            "hf_safetensors: snapshot unavailable for %s@%s: %s",
            model_id,
            revision or "default",
            e,
        )
        return False

    if (root / "model.safetensors").exists() or (
        root / "model.safetensors.index.json"
    ).exists():
        return True

    bin_path = root / "pytorch_model.bin"
    if not bin_path.exists():
        return False

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
            return False
        tensors = {
            k: v.contiguous()
            for k, v in state.items()
            if hasattr(v, "contiguous") and hasattr(v, "dtype")
        }
        if not tensors:
            return False
        save_file(tensors, str(tmp_path))
        tmp_path.replace(out_path)
        log.info(
            "Converted %s pytorch_model.bin → model.safetensors for torch<2.6 load",
            model_id,
        )
        return True
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
        return False
