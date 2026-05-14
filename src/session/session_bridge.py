"""SessionBridge — sync facade over the async SessionRunner.

Sits between the pywebview JS-Bridge (synchronous calls) and the asyncio
SessionRunner. Owns:
 - a background asyncio loop in its own thread,
 - a TCodeClient connection to Restim,
 - the active SessionRunner instance.

Sidebar JS calls the sync methods; bridge forwards them onto the loop.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import asdict
from typing import Callable, Optional

from .profile import SessionProfile
from .session_runner import SessionRunner, SessionStatus

logger = logging.getLogger("session.bridge")


class SessionBridge:
    """Sync API wrapping an async SessionRunner. Thread-safe."""

    def __init__(self, restim_url: str = "ws://127.0.0.1:12346/tcode",
                 on_log: Optional[Callable[[str], None]] = None,
                 on_status: Optional[Callable[[SessionStatus], None]] = None):
        self.restim_url = restim_url
        self._on_log = on_log or (lambda msg: None)
        self._on_status = on_status or (lambda s: None)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._tcode_client = None
        self._runner: Optional[SessionRunner] = None
        self._current_session_task: Optional[asyncio.Task] = None
        self._profile_draft: Optional[SessionProfile] = None
        self._envelope_draft: Optional[dict] = None

    # ---- Lifecycle ----

    def start(self) -> None:
        """Start the background asyncio loop and connect TCodeClient."""
        if self._loop_thread is not None:
            return

        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True, name="SessionLoop")
        self._loop_thread.start()
        # Wait briefly for loop to be ready
        for _ in range(50):
            if self._loop is not None:
                break
            import time
            time.sleep(0.02)

        # Connect TCode client (lazy import to avoid cycles)
        from src.restim.tcode_client import TCodeClient
        self._tcode_client = TCodeClient(url=self.restim_url, on_log=self._on_log)
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._tcode_client.connect(), self._loop)

    def stop(self) -> None:
        """Stop any active session and shut down the loop."""
        if self._loop is None:
            return
        if self._runner and self._runner.is_running():
            self._runner.stop()
        if self._tcode_client:
            asyncio.run_coroutine_threadsafe(self._tcode_client.disconnect(), self._loop)

        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread:
            self._loop_thread.join(timeout=2.0)
        self._loop = None
        self._loop_thread = None

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_forever()
        finally:
            try:
                loop.close()
            except Exception:
                pass

    # ---- Profile draft management (called from JS as user edits sliders) ----

    def set_session_profile(self, profile_dict: dict) -> bool:
        """Stores the configured profile as 'draft'. start_session() picks it up."""
        try:
            # Allow envelope to be passed as a separate field (JS sends both together)
            envelope = profile_dict.pop("envelope", None) if isinstance(profile_dict, dict) else None
            self._profile_draft = self._profile_from_dict(profile_dict)
            if envelope is not None:
                self._envelope_draft = envelope
            return True
        except Exception as e:
            self._on_log(f"set_session_profile error: {e}")
            return False

    def update_session_envelope(self, envelope_json_str: str) -> bool:
        """JS sends new master-line + drops after each drag."""
        import json
        try:
            self._envelope_draft = json.loads(envelope_json_str)
            return True
        except Exception as e:
            self._on_log(f"update_session_envelope error: {e}")
            return False

    def get_session_profile_dict(self) -> dict:
        """For JS to read back the current draft (e.g. on init)."""
        if self._profile_draft is None:
            return asdict(SessionProfile())
        return asdict(self._profile_draft)

    # ---- Session lifecycle ----

    def start_session(self, profile_dict: Optional[dict] = None) -> bool:
        """Start the session immediately. profile_dict is optional override."""
        if self._loop is None:
            self._on_log("Session loop not running")
            return False
        if self._runner and self._runner.is_running():
            self._on_log("Session already running")
            return False

        if profile_dict is not None:
            envelope = profile_dict.pop("envelope", None) if isinstance(profile_dict, dict) else None
            try:
                self._profile_draft = self._profile_from_dict(profile_dict)
                if envelope is not None:
                    self._envelope_draft = envelope
            except Exception as e:
                self._on_log(f"start_session profile parse error: {e}")
                return False

        if self._profile_draft is None:
            self._on_log("No profile configured")
            return False

        if self._tcode_client is None:
            self._on_log("TCode client not initialized")
            return False

        # Create runner
        self._runner = SessionRunner(
            tcode_send=self._tcode_client.send,
            on_status=self._on_status,
        )

        # Apply envelope if present (override macro intensity curve points)
        profile = self._profile_draft
        future = asyncio.run_coroutine_threadsafe(self._runner.start(profile), self._loop)
        self._current_session_task = future
        self._on_log(f"Session started: {profile.style.value}, {profile.duration_s}s")
        return True

    def session_pause(self) -> None:
        if self._runner:
            self._runner.pause()

    def session_resume(self) -> None:
        if self._runner:
            self._runner.resume()

    def session_skip(self) -> None:
        if self._runner:
            self._runner.skip_phase()

    def session_edge_now(self) -> None:
        if self._runner:
            self._runner.edge_now()

    def session_boost(self) -> None:
        if self._runner:
            self._runner.boost()

    def session_stop(self) -> None:
        if self._runner:
            self._runner.stop()

    def session_panic(self) -> None:
        if self._runner:
            self._runner.panic_stop()

    def is_running(self) -> bool:
        return self._runner is not None and self._runner.is_running()

    # ---- Helpers ----

    def _profile_from_dict(self, d: dict) -> SessionProfile:
        """Coerce a JS-sent dict (from sidebar) into a SessionProfile."""
        from .profile import (AdvancedSettings, Electrode, HardwareProfile,
                              SafetyCaps, SensationMix)
        from .types import (Character, DeviceClass, ElectrodePosition,
                            ExperienceLevel, SessionStyle, SessionTarget)

        # Sensation defaults — JS may send keys "sharp_to_deep" etc., or under "sensation"
        sm_raw = d.get("sensation", {}) if isinstance(d.get("sensation", {}), dict) else {}
        sm = SensationMix(
            sharp_to_deep=float(sm_raw.get("sharp_to_deep", 0.5)),
            granular_to_smooth=float(sm_raw.get("granular_to_smooth", 0.5)),
            soft_to_hard=float(sm_raw.get("soft_to_hard", 0.5)),
            static_to_moving=float(sm_raw.get("static_to_moving", 0.5)),
        )

        # Hardware
        hw_raw = d.get("hardware", {}) if isinstance(d.get("hardware", {}), dict) else {}
        electrodes_raw = hw_raw.get("electrodes", [])
        size_map = {"small": 4.0, "medium": 9.0, "large": 16.0}
        electrodes = []
        for e in electrodes_raw:
            try:
                electrodes.append(Electrode(
                    position=ElectrodePosition(e["position"]),
                    is_common=bool(e.get("is_common", False)),
                    size_cm2=size_map.get(e.get("size", "medium"), 9.0)
                    if isinstance(e.get("size"), str)
                    else float(e.get("size_cm2", 9.0)),
                ))
            except Exception:
                continue
        hw = HardwareProfile(
            device_class=DeviceClass(hw_raw.get("device_class", DeviceClass.THREE_PHASE_FOC.value)),
            electrodes=electrodes,
        )

        # Safety + advanced
        safety_raw = d.get("safety", {}) if isinstance(d.get("safety", {}), dict) else {}
        safety = SafetyCaps(
            max_volume=float(safety_raw.get("max_volume", 1.0)),
            max_carrier_hz=float(safety_raw.get("max_carrier_hz", 2200.0)),
            max_pulse_width_us=float(safety_raw.get("max_pulse_width_us", 400.0)),
            min_volume_ramp_s=float(safety_raw.get("min_volume_ramp_s", 5.0)),
        )

        adv_raw = d.get("advanced", {}) if isinstance(d.get("advanced", {}), dict) else {}
        advanced = AdvancedSettings(
            pattern_repeat_lockout_s=adv_raw.get("pattern_repeat_lockout_s"),
            crossfade_s=adv_raw.get("crossfade_s"),
            pattern_pool=adv_raw.get("pattern_pool"),
            subwave_count=adv_raw.get("subwave_count"),
        )

        return SessionProfile(
            style=SessionStyle(d.get("style", SessionStyle.SANFTER_AUFBAU.value)),
            duration_s=int(d.get("duration_s", 45 * 60)),
            target=SessionTarget(d.get("target", SessionTarget.CLIMAX.value)),
            sensation=sm,
            character=Character(d.get("character", Character.LEBENDIG.value)),
            experience=ExperienceLevel(int(d.get("experience", 2))),
            hardware=hw,
            safety=safety,
            advanced=advanced,
            seed=d.get("seed"),
        )
