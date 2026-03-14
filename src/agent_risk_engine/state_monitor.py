"""StateMonitor — Layer 3: System state awareness.

Protocol and stub implementation. Future implementations will track
context window usage, rate limits, loop detection, etc.
Framework-agnostic — no imports from squire or any agent framework.
"""

from typing import Protocol

from .models import SystemState


class StateMonitor(Protocol):
    """Monitors system health for risk-relevant conditions."""

    def check(self) -> SystemState:
        """Check current system state and return risk-relevant signals.

        Returns:
            SystemState with health status, warnings, and risk adjustment.
        """
        ...


class NullStateMonitor:
    """Stub monitor that always reports healthy state."""

    def check(self) -> SystemState:
        return SystemState()
