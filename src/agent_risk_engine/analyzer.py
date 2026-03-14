"""ToolAnalyzer — Layer 2: Argument-aware risk analysis.

Protocol and stub implementation. Future implementations will use an LLM
to evaluate the actual risk of specific tool call arguments.
Framework-agnostic — no imports from squire or any agent framework.
"""

from typing import Protocol

from .models import RiskScore


class ToolAnalyzer(Protocol):
    """Analyzes the actual risk of a specific tool call based on its arguments."""

    async def analyze(self, tool_name: str, args: dict, tool_risk: int) -> RiskScore:
        """Evaluate the risk of a tool call with its specific arguments.

        Args:
            tool_name: The name of the tool being invoked.
            args: The arguments being passed to the tool.
            tool_risk: The static risk level assigned to the tool (1-5).

        Returns:
            RiskScore with evaluated risk level and reasoning.
        """
        ...


class PassthroughAnalyzer:
    """Stub analyzer that returns the tool's static risk level unchanged."""

    async def analyze(self, tool_name: str, args: dict, tool_risk: int) -> RiskScore:
        return RiskScore(level=tool_risk)
