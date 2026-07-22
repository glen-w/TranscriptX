"""Lifecycle-managed SpeakerStudioController for Streamlit pages.

ClipService creates a ThreadPoolExecutor and cache-pruning thread on init.
Constructing a new controller on every full Streamlit rerun leaks those
resources. Prefer ``get_shared_speaker_studio_controller`` so pages share one
instance for the process lifetime.
"""

from __future__ import annotations

import atexit
import threading

import streamlit as st

from transcriptx.services.speaker_studio.controller import SpeakerStudioController

_atexit_registered = False
_atexit_lock = threading.Lock()
_registry_lock = threading.Lock()
_registered_controllers: set[SpeakerStudioController] = set()


def _register_controller(controller: SpeakerStudioController) -> None:
    with _registry_lock:
        _registered_controllers.add(controller)


def _unregister_controller(controller: SpeakerStudioController) -> None:
    with _registry_lock:
        _registered_controllers.discard(controller)


def _close_registered_controllers() -> None:
    """Close every shared controller still registered (process exit)."""
    with _registry_lock:
        controllers = list(_registered_controllers)
        _registered_controllers.clear()
    for controller in controllers:
        try:
            controller.close()
        except Exception:
            pass


def _register_atexit_close(
    controller: SpeakerStudioController | None = None,
) -> None:
    """
    Register a controller for process-exit cleanup.

    When ``controller`` is provided it is added to the registry. The atexit
    handler is registered once and closes *all* registered instances.
    """
    global _atexit_registered
    if controller is not None:
        _register_controller(controller)
    with _atexit_lock:
        if _atexit_registered:
            return
        atexit.register(_close_registered_controllers)
        _atexit_registered = True


@st.cache_resource(show_spinner=False)
def get_shared_speaker_studio_controller() -> SpeakerStudioController:
    """Return a process-scoped SpeakerStudioController (executor-safe).

    Streamlit caches the returned object. Callers must receive a live
    ``SpeakerStudioController``, not a generator.
    """
    controller = SpeakerStudioController()
    _register_atexit_close(controller)
    return controller


def clear_shared_speaker_studio_controller() -> None:
    """Close the cached shared controller, then clear the Streamlit resource cache."""
    with _registry_lock:
        controllers = list(_registered_controllers)
    for controller in controllers:
        try:
            controller.close()
        except Exception:
            pass
        _unregister_controller(controller)
    get_shared_speaker_studio_controller.clear()  # type: ignore[attr-defined]
