# agent-risk-engine

A layered protocol and reference implementation for codifying risk in autonomous agent actions.

See [PROTOCOL.md](https://github.com/willdah/agent-risk-engine/blob/main/PROTOCOL.md) for the language-agnostic protocol specification.

## Installation

### uv
```bash
uv add agent-risk-engine
```

### pip
```bash
pip install agent-risk-engine
```

## Quick Start

```python
from agent_risk_engine import RuleGate, RiskEvaluator, Action, GateResult

gate = RuleGate(threshold="cautious")
evaluator = RiskEvaluator(rule_gate=gate)

result = await evaluator.evaluate(Action(kind="tool_call", name="read_file", risk=1))
assert result.decision == GateResult.ALLOWED

result = await evaluator.evaluate(
    Action(kind="tool_call", name="execute_shell", parameters={"command": "rm -rf /"}, risk=5)
)
assert result.decision == GateResult.NEEDS_APPROVAL
```

## Architecture

Actions pass through a 3-layer pipeline:

```
Action --> RuleGate (L1) --> ActionAnalyzer (L2) --> ActionGate (L3) --> Decision
              |                                                           |
              +-- DENIED (short-circuit) ---------------------------------+
```

| Layer | Component          | Role                              | Speed        |
|-------|--------------------|-----------------------------------|--------------|
| L1    | **RuleGate**       | Fast static rules — no LLM        | Microseconds |
| L2    | **ActionAnalyzer** | Argument-aware scoring (Protocol)  | Varies       |
| L3    | **ActionGate**     | Risk vs utility tradeoff           | Microseconds |

**L1 (RuleGate)** and the **RiskUtilityGate** implementation of L3 are fully implemented. L2 ships as a passthrough stub — plug in your own `ActionAnalyzer`. Layers only escalate, never relax — a DENIED from L1 short-circuits the entire pipeline.

## Risk Levels

| Level | Label    | Meaning                          |
|-------|----------|----------------------------------|
| 1     | Info     | Read-only, no side effects       |
| 2     | Low      | Reads potentially sensitive data |
| 3     | Moderate | Reversible mutations             |
| 4     | High     | Hard-to-reverse mutations        |
| 5     | Critical | Destructive or irreversible      |

Use the `RiskLevel` enum for readable risk assignments:

```python
from agent_risk_engine import RiskLevel

Action(kind="tool_call", name="read_file", risk=RiskLevel.INFO)      # 1
Action(kind="tool_call", name="delete_db", risk=RiskLevel.CRITICAL)  # 5
```

## RuleGate

Fast, deterministic, no LLM required. Supports per-kind threshold routing:

```python
gate = RuleGate(
    threshold="cautious",
    kind_thresholds={
        "tool_call": "standard",
        "file_write": 2,
        "code_execution": 1,
    },
    denied={"delete_database"},
    allowed={"read_logs"},
    approve={"send_email"},
)
```

Evaluation order: `denied` → `allowed` → `approve` → threshold comparison.

### Strict Mode

By default, actions above the threshold require approval (`NEEDS_APPROVAL`). With `strict=True`, they are denied outright:

```python
gate = RuleGate(threshold="cautious", strict=True)
# risk=3 action -> DENIED (instead of NEEDS_APPROVAL)
```

### Threshold Aliases

| Alias        | Level | Description                     |
|--------------|-------|---------------------------------|
| `read-only`  | 1     | Only info-level actions         |
| `cautious`   | 2     | Info + low-risk actions         |
| `standard`   | 3     | Up to reversible mutations      |
| `full-trust` | 5     | Everything auto-allowed         |

## PatternAnalyzer

Scores actions by matching regex patterns against serialized parameters. Supports kind-scoped patterns:

```python
from agent_risk_engine import PatternAnalyzer, RiskPattern

analyzer = PatternAnalyzer(extra_patterns=[
    RiskPattern(r"\bDROP\b", 5, "SQL drop", kinds=frozenset({"database_query"})),
])
```

Pass it to `RiskEvaluator(rule_gate=gate, action_analyzer=analyzer)`.

## RiskUtilityGate

Weighs risk against caller-provided utility. Utility is an **input**, not computed internally — the library evaluates risk; your framework understands agent goals.

```python
evaluator = RiskEvaluator(
    rule_gate=RuleGate(threshold="standard"),
    action_gate=RiskUtilityGate(),
)

result = await evaluator.evaluate(
    Action(kind="tool_call", name="write_file", risk=3),
    utility=UtilityScore(level=4, reasoning="User explicitly requested"),
)
```

The gate **only escalates, never relaxes** — it cannot make a decision less restrictive than L1.

## Extending with Custom Analyzers

`ActionAnalyzer` is a `Protocol`. Implement `analyze(action: Action) -> RiskScore`:

```python
from agent_risk_engine import RiskEvaluator, RuleGate, RiskScore, Action

class LLMAnalyzer:
    """Use an LLM to evaluate the actual risk of action arguments."""

    async def analyze(self, action: Action) -> RiskScore:
        # Inspect action.parameters, reason about consequences
        assessed_level = await my_llm_judge(action.name, action.parameters)
        return RiskScore(level=assessed_level, reasoning="LLM analysis")

evaluator = RiskEvaluator(
    rule_gate=RuleGate(threshold="cautious"),
    action_analyzer=LLMAnalyzer(),
)
```

## CallTracker

Standalone loop and repetition detection. Not a pipeline layer — use it to build context before evaluating:

```python
from agent_risk_engine import CallTracker

tracker = CallTracker(window=20, loop_threshold=3, repetition_ratio=0.7)
tracker.record(action.name)
context = tracker.check()
# context: {"healthy": bool, "warnings": list[str]}

# Merge into action metadata before evaluating
action = Action(kind=action.kind, name=action.name, risk=action.risk, metadata=context)
```

- `window` — number of recent calls to retain (default 20)
- `loop_threshold` — consecutive identical calls to flag a loop (default 3)
- `repetition_ratio` — fraction of calls to one action that triggers a warning (default 0.7)

## ActionRegistry

Optional lookup table for action risk levels. Use it as the source of truth for your action catalog:

```python
from agent_risk_engine import ActionRegistry

registry = ActionRegistry(default_risk=5)
registry.register("read_file", kind="tool_call", risk=1, description="Read a file")
registry.register("delete_file", kind="file_delete", risk=4)

# Look up risk for an action
risk = registry.get_risk("read_file")    # 1
risk = registry.get_risk("unknown_tool") # 5 (default_risk)
```

The registry is not wired into the pipeline automatically — use it to build `Action` objects with correct risk levels before evaluating.

## Framework Integration

Write a thin adapter that maps your framework's action primitives to `Action`:

```python
async def before_action_hook(action_name, args, action_risk):
    action = Action(kind="tool_call", name=action_name, parameters=args, risk=action_risk)
    result = await evaluator.evaluate(action)

    if result.decision == GateResult.DENIED:
        raise PermissionError(result.reasoning)
    if result.decision == GateResult.NEEDS_APPROVAL:
        approved = await prompt_user(f"Allow '{action_name}'? Risk: {result.risk_score.level}/5")
        if not approved:
            raise PermissionError("User denied")
```

## License

MIT
