"""Central management of the Hugging Face models Laminar depends on.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

TEXT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CODE_MODEL_NAME = "microsoft/codebert-base"
REQUIRED_MODELS = (TEXT_MODEL_NAME, CODE_MODEL_NAME)

_WEIGHT_FILES = (
    "model.safetensors",
    "pytorch_model.bin",
    "tf_model.h5",
    "flax_model.msgpack",
)

StatusCallback = Optional[Callable[[str], None]]


class ModelSetupError(RuntimeError):
    """Raised when a required model cannot be downloaded or loaded."""


def _cached_file(model_name: str, filename: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except Exception:
        return False
    try:
        return isinstance(try_to_load_from_cache(model_name, filename), str)
    except Exception:
        return False


def _is_cached(model_name: str) -> bool:
    """Best-effort check for whether *model_name* is fully cached locally."""
    if not _cached_file(model_name, "config.json"):
        return False
    return any(_cached_file(model_name, w) for w in _WEIGHT_FILES)


def models_are_available() -> bool:
    """Return True if every required model appears to be fully cached locally."""
    return all(_is_cached(name) for name in REQUIRED_MODELS)


def _emit(status_cb: StatusCallback, message: str) -> None:
    if status_cb is not None:
        status_cb(message)
    else:
        print(message, file=sys.stderr, flush=True)


def ensure_models_available(status_cb: StatusCallback = None,
                            show_progress: bool = True) -> None:
    """Make sure every required model is downloaded and loadable.
    """
    try:
        from transformers import AutoModel, AutoTokenizer
    except Exception as exc:  # pragma: no cover - transformers is a hard dep
        raise ModelSetupError(
            f"transformers is not importable, cannot load models: {exc}") from exc

    if not show_progress:
        try:
            from huggingface_hub.utils import disable_progress_bars
            disable_progress_bars()
        except Exception:
            pass

    total = len(REQUIRED_MODELS)
    for idx, name in enumerate(REQUIRED_MODELS, start=1):
        if _is_cached(name):
            _emit(status_cb, f"[{idx}/{total}] Model already available: {name}")
            continue

        _emit(status_cb,
              f"[{idx}/{total}] Downloading model '{name}' (first run only)…")
        try:
            AutoTokenizer.from_pretrained(name)
            AutoModel.from_pretrained(name)
        except Exception as exc:
            raise ModelSetupError(
                f"Failed to download or load required model '{name}': {exc}"
            ) from exc
        _emit(status_cb, f"[{idx}/{total}] Ready: {name}")

    _emit(status_cb, "All required models are downloaded and available.")
