"""ActionGate — Layer 4: Final integration gate.

Protocol and stub implementation. Future implementations will weigh
risk scores against utility and system state for a final go/no-go decision.
Framework-agnostic — no imports from squire or any agent framework.
"""

from typing import Protocol

from .models import GateResult, RiskScore, SystemState


class ActionGate(Protocol):
    """Final decision gate integrating all risk signals."""

    def decide(
        self,
        rule_result: GateResult,
        risk_score: RiskScore,
        system_state: SystemState,
    ) -> GateResult:
        """Make the final go/no-go decision.

        Args:
            rule_result: The RuleGate's initial decision.
            risk_score: The ToolAnalyzer's evaluated risk.
            system_state: Current system health from StateMonitor.

        Returns:
            Final GateResult.
        """
        ...


class PassthroughActionGate:
    """Stub gate that defers to the RuleGate's decision."""

    def decide(
        self,
        rule_result: GateResult,
        risk_score: RiskScore,
        system_state: SystemState,
    ) -> GateResult:
        return rule_result
