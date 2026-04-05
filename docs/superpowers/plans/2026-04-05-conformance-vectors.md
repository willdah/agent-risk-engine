# Conformance Test Vectors Implementation Plan

> **Note:** This plan predates the risk tolerance elevation — shipped config uses `risk_tolerance`/`kind_tolerances` instead of `threshold`/`kind_thresholds`, and category names use `tolerance-boundary`/`kind-tolerances` instead of `threshold-boundary`/`kind-thresholds`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `conformance/` directory with protocol-tier and reference-tier JSON test vectors that define correct behavior for the Agent Risk Protocol, plus two normative utility constraints added to the protocol spec.

**Architecture:** Two JSON files (`protocol.json`, `reference.json`) with a shared vector schema, a `README.md` documenting the schema and usage, two new normative constraints in `PROTOCOL.md`, and a one-line implementation change to enforce the stricter utility offset limit.

**Tech Stack:** JSON (vectors), Markdown (README, protocol), Python (one-line implementation fix + test updates)

---

### Task 1: Enforce utility offset limit in RiskUtilityGate

The implementation currently allows utility to offset risk by up to 2 escalation levels. Change this to 1 to match the new normative constraint.

**Files:**
- Modify: `src/agent_risk_engine/action_gate.py:66`
- Modify: `tests/test_utility_gate.py:81-104`

- [ ] **Step 1: Update the existing tests to expect the new behavior**

In `tests/test_utility_gate.py`, rename `TestGapTwo` to `TestLargeGap` and update the expected results. The class currently expects `denied` for gap >= 2, but with `min(gap, 1)` clamping, gap >= 2 from `allowed` should produce `needs_approval` (one step), not `denied` (two steps).

Replace the `TestGapTwo` class (lines 81-104) with:

```python
class TestLargeGap:
    def test_gap_two_from_allowed(self, gate):
        """Gap of 2: only escalates one step (allowed -> needs_approval)."""
        result = gate.decide(
            GateResult.ALLOWED,
            RiskScore(level=4),
            utility=UtilityScore(level=2),
        )
        assert result == GateResult.NEEDS_APPROVAL

    def test_gap_two_from_needs_approval(self, gate):
        """Gap of 2 from needs_approval: escalates one step to denied."""
        result = gate.decide(
            GateResult.NEEDS_APPROVAL,
            RiskScore(level=5),
            utility=UtilityScore(level=3),
        )
        assert result == GateResult.DENIED

    def test_large_gap_clamps_at_one_step(self, gate):
        """Gap of 4: still only escalates one step from allowed."""
        result = gate.decide(
            GateResult.ALLOWED,
            RiskScore(level=5),
            utility=UtilityScore(level=1),
        )
        assert result == GateResult.NEEDS_APPROVAL
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_utility_gate.py::TestLargeGap -v`

Expected: 2 of 3 fail — `test_gap_two_from_allowed` and `test_large_gap_clamps_at_one_step` return `denied` instead of `needs_approval`.

- [ ] **Step 3: Change the escalation cap from 2 to 1**

In `src/agent_risk_engine/action_gate.py`, line 66, change:

```python
        steps = min(gap, 2)
```

to:

```python
        steps = min(gap, 1)
```

- [ ] **Step 4: Run the full test suite to verify everything passes**

Run: `uv run pytest -v`

Expected: All tests pass. The parametric sweep in `TestParametricSweep` should still pass because it only asserts the never-relaxes invariant, not specific escalation amounts.

- [ ] **Step 5: Commit**

```bash
git add src/agent_risk_engine/action_gate.py tests/test_utility_gate.py
git commit -m "feat: cap utility offset at 1 escalation level

Enforces normative constraint: utility MUST NOT reduce the effective
decision by more than one escalation level. Changes min(gap, 2) to
min(gap, 1) in RiskUtilityGate."
```

---

### Task 2: Add normative utility constraints to PROTOCOL.md

**Files:**
- Modify: `PROTOCOL.md:68-80`

- [ ] **Step 1: Add the two new evaluation semantics**

In `PROTOCOL.md`, after item 5 ("Secure by default", line 80) and before the `## Recommended Action Kinds` heading (line 82), insert:

```markdown

6. **Utility offset limit.** Utility MUST NOT reduce the effective decision by more than one escalation level relative to what risk alone would produce. An action that risk evaluation would deny may be relaxed to needs_approval by sufficient utility, but never directly to allowed.

7. **Critical risk protection.** Risk level 5 actions MUST NOT be resolved as `allowed` by utility alone. Only explicit developer rules (allow lists) may auto-allow critical-risk actions.
```

- [ ] **Step 2: Update the Conformance section to reference the new semantics**

In `PROTOCOL.md`, line 119, change:

```markdown
4. It respects all evaluation semantics (escalation-only, denied-is-final, stateless, developer-rules-first, secure-by-default)
```

to:

```markdown
4. It respects all evaluation semantics (escalation-only, denied-is-final, stateless, developer-rules-first, secure-by-default, utility-offset-limit, critical-risk-protection)
```

- [ ] **Step 3: Commit**

```bash
git add PROTOCOL.md
git commit -m "protocol: add utility offset limit and critical risk protection semantics

Two new normative constraints:
- Utility MUST NOT reduce decisions by more than one escalation level
- Risk level 5 actions MUST NOT be resolved as allowed by utility alone"
```

---

### Task 3: Create conformance directory and README

**Files:**
- Create: `conformance/README.md`

- [ ] **Step 1: Create the conformance README**

Create `conformance/README.md` with the following content:

```markdown
# Agent Risk Protocol — Conformance Vectors

Machine-readable test vectors that define correct behavior for the Agent Risk Protocol.

## Files

| File | Audience | Description |
|------|----------|-------------|
| `protocol.json` | All implementors | Universal protocol semantics — any conforming implementation in any language must pass these |
| `reference.json` | Python / reference impl users | Behavior specific to the Python reference implementation (PatternAnalyzer, RiskUtilityGate, full pipeline) |

## Vector Schema

Each file contains:

```json
{
  "version": "1.0.0",
  "description": "Human-readable file description",
  "vectors": [...]
}
```

Each vector:

```json
{
  "id": "protocol-rule-gate-001",
  "description": "What this vector tests",
  "category": "semantic-category",
  "config": { ... },
  "action": { "kind": "...", "name": "...", "parameters": {}, "risk": 1 },
  "utility": null,
  "expected": { "decision": "allowed" }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique ID, prefixed by tier and component |
| `description` | string | yes | What the vector tests |
| `category` | string | yes | Semantic grouping for reporting |
| `config` | object | yes | Evaluator configuration (see below) |
| `action` | object | yes | Action envelope |
| `utility` | object/null | yes | Utility score or null |
| `expected` | object | yes | Expected outcome |

### Config

Protocol-tier vectors use `rule_gate` only:

```json
{
  "rule_gate": {
    "threshold": 3,
    "strict": false,
    "allowed": [],
    "approve": [],
    "denied": [],
    "kind_thresholds": {}
  }
}
```

All fields except `threshold` are optional (default to empty/false).

Reference-tier vectors may add `analyzer` and `action_gate`:

```json
{
  "analyzer": { "type": "pattern", "include_defaults": true, "extra_patterns": [] },
  "action_gate": { "type": "risk_utility" }
}
```

### Expected

Protocol-tier: `{"decision": "allowed|needs_approval|denied"}`

Reference-tier may add: `{"decision": "...", "risk_score_level": 5}`

### Categories

**Protocol-tier:**
- `denied-is-final` — denied-set always produces denied
- `evaluation-order` — denied > allowed > approve > threshold
- `threshold-boundary` — at/below/above threshold behavior
- `kind-thresholds` — per-kind threshold overrides
- `escalation-only` — later stages can only escalate
- `secure-by-default` — unknown actions default to highest risk
- `utility-constraints` — utility offset and critical risk limits

**Reference-tier:**
- `pattern-escalation` — PatternAnalyzer risk bumping
- `pattern-invariant` — escalation-only in analyzer
- `pattern-kind-scoping` — kind-filtered patterns
- `risk-utility-formula` — RiskUtilityGate behavior
- `full-pipeline` — end-to-end RiskEvaluator
```

- [ ] **Step 2: Commit**

```bash
git add conformance/README.md
git commit -m "docs: add conformance vectors README with schema documentation"
```

---

### Task 4: Write protocol.json vectors

**Files:**
- Create: `conformance/protocol.json`

- [ ] **Step 1: Create protocol.json with all 30 vectors**

Create `conformance/protocol.json` with the following content:

```json
{
  "version": "1.0.0",
  "description": "Conformance vectors for Agent Risk Protocol — universal semantics. Any conforming implementation must pass these.",
  "vectors": [
    {
      "id": "protocol-denied-001",
      "description": "Denied-set action is denied regardless of low risk",
      "category": "denied-is-final",
      "config": { "rule_gate": { "threshold": 5, "denied": ["drop_database"] } },
      "action": { "kind": "tool_call", "name": "drop_database", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-denied-002",
      "description": "Denied-set overrides allowed-set when name is in both",
      "category": "denied-is-final",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"], "allowed": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-denied-003",
      "description": "Denied-set overrides approve-set when name is in both",
      "category": "denied-is-final",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"], "approve": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-denied-004",
      "description": "Denied-set overrides when name is in all three sets",
      "category": "denied-is-final",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"], "allowed": ["x"], "approve": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-denied-005",
      "description": "Denied-set action denied even at full-trust threshold",
      "category": "denied-is-final",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },

    {
      "id": "protocol-order-001",
      "description": "Allowed-set bypasses threshold even for risk 5 with threshold 1",
      "category": "evaluation-order",
      "config": { "rule_gate": { "threshold": 1, "allowed": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-order-002",
      "description": "Allowed-set overrides approve-set when name is in both",
      "category": "evaluation-order",
      "config": { "rule_gate": { "threshold": 1, "allowed": ["x"], "approve": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-order-003",
      "description": "Approve-set forces needs_approval even when threshold would allow",
      "category": "evaluation-order",
      "config": { "rule_gate": { "threshold": 5, "approve": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-order-004",
      "description": "Action not in any set falls through to threshold comparison",
      "category": "evaluation-order",
      "config": { "rule_gate": { "threshold": 3 } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 4 },
      "utility": null,
      "expected": { "decision": "needs_approval" }
    },

    {
      "id": "protocol-threshold-001",
      "description": "Risk exactly at threshold is allowed",
      "category": "threshold-boundary",
      "config": { "rule_gate": { "threshold": 3 } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-threshold-002",
      "description": "Risk below threshold is allowed",
      "category": "threshold-boundary",
      "config": { "rule_gate": { "threshold": 3 } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-threshold-003",
      "description": "Risk above threshold in non-strict mode is needs_approval",
      "category": "threshold-boundary",
      "config": { "rule_gate": { "threshold": 3, "strict": false } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 4 },
      "utility": null,
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-threshold-004",
      "description": "Risk above threshold in strict mode is denied",
      "category": "threshold-boundary",
      "config": { "rule_gate": { "threshold": 3, "strict": true } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 4 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-threshold-005",
      "description": "Threshold 5 allows everything",
      "category": "threshold-boundary",
      "config": { "rule_gate": { "threshold": 5 } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },

    {
      "id": "protocol-kind-001",
      "description": "Kind threshold overrides default threshold",
      "category": "kind-thresholds",
      "config": { "rule_gate": { "threshold": 1, "kind_thresholds": { "tool_call": 3 } } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-kind-002",
      "description": "Unknown kind falls back to default threshold",
      "category": "kind-thresholds",
      "config": { "rule_gate": { "threshold": 1, "kind_thresholds": { "tool_call": 3 } } },
      "action": { "kind": "file_write", "name": "x", "parameters": {}, "risk": 2 },
      "utility": null,
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-kind-003",
      "description": "Kind threshold respects strict mode",
      "category": "kind-thresholds",
      "config": { "rule_gate": { "threshold": 1, "strict": true, "kind_thresholds": { "tool_call": 2 } } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-kind-004",
      "description": "Name override takes precedence over kind threshold",
      "category": "kind-thresholds",
      "config": { "rule_gate": { "threshold": 1, "kind_thresholds": { "tool_call": 1 }, "allowed": ["x"] } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },

    {
      "id": "protocol-escalation-001",
      "description": "Layer 3 can escalate allowed to needs_approval",
      "category": "escalation-only",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 2, "reasoning": "Low utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-escalation-002",
      "description": "Layer 3 can escalate needs_approval to denied",
      "category": "escalation-only",
      "config": { "rule_gate": { "threshold": 2 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 2, "reasoning": "Low utility" },
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-escalation-003",
      "description": "Layer 3 cannot relax needs_approval to allowed even with high utility",
      "category": "escalation-only",
      "config": { "rule_gate": { "threshold": 2 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 5, "reasoning": "Very high utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-escalation-004",
      "description": "Layer 3 cannot relax denied to needs_approval even with high utility",
      "category": "escalation-only",
      "config": { "rule_gate": { "threshold": 2, "strict": true }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 5, "reasoning": "Very high utility" },
      "expected": { "decision": "denied" }
    },

    {
      "id": "protocol-default-001",
      "description": "Unknown action at default threshold needs approval (risk defaults to highest)",
      "category": "secure-by-default",
      "config": { "rule_gate": { "threshold": 2 } },
      "action": { "kind": "tool_call", "name": "unknown_action", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-default-002",
      "description": "Unknown action at default threshold in strict mode is denied",
      "category": "secure-by-default",
      "config": { "rule_gate": { "threshold": 2, "strict": true } },
      "action": { "kind": "tool_call", "name": "unknown_action", "parameters": {}, "risk": 5 },
      "utility": null,
      "expected": { "decision": "denied" }
    },

    {
      "id": "protocol-utility-001",
      "description": "Utility cannot relax a denied result",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"] }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": { "level": 5, "reasoning": "Maximum utility" },
      "expected": { "decision": "denied" }
    },
    {
      "id": "protocol-utility-002",
      "description": "Utility cannot relax below rule gate output",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 2 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 5, "reasoning": "Maximum utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-utility-003",
      "description": "Risk 5 action above threshold cannot be made allowed by utility alone",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 4 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": { "level": 5, "reasoning": "Maximum utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-utility-004",
      "description": "Risk 4 with utility 5 stays at rule gate output (no relaxation by utility)",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 3 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 4 },
      "utility": { "level": 5, "reasoning": "Maximum utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "protocol-utility-005",
      "description": "Equal risk and utility produces no escalation from utility",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 3, "reasoning": "Matched utility" },
      "expected": { "decision": "allowed" }
    },
    {
      "id": "protocol-utility-006",
      "description": "Risk exceeding utility causes escalation",
      "category": "utility-constraints",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 4 },
      "utility": { "level": 2, "reasoning": "Low utility" },
      "expected": { "decision": "needs_approval" }
    }
  ]
}
```

- [ ] **Step 2: Validate JSON is well-formed**

Run: `python3 -c "import json; d = json.load(open('conformance/protocol.json')); print(f'{len(d[\"vectors\"])} vectors loaded')"`

Expected: `30 vectors loaded`

- [ ] **Step 3: Verify all vector IDs are unique**

Run: `python3 -c "import json; d = json.load(open('conformance/protocol.json')); ids = [v['id'] for v in d['vectors']]; dupes = [i for i in ids if ids.count(i) > 1]; print('OK' if not dupes else f'Duplicates: {set(dupes)}')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add conformance/protocol.json
git commit -m "feat: add protocol-tier conformance vectors (30 cases)

Covers: denied-is-final, evaluation-order, threshold-boundary,
kind-thresholds, escalation-only, secure-by-default, utility-constraints"
```

---

### Task 5: Write reference.json vectors

**Files:**
- Create: `conformance/reference.json`

- [ ] **Step 1: Create reference.json with all 21 vectors**

Create `conformance/reference.json` with the following content:

```json
{
  "version": "1.0.0",
  "description": "Conformance vectors for the Python reference implementation — PatternAnalyzer, RiskUtilityGate, and full RiskEvaluator pipeline.",
  "vectors": [
    {
      "id": "reference-pattern-001",
      "description": "rm -rf in parameters escalates to risk 5",
      "category": "pattern-escalation",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "exec", "parameters": { "command": "rm -rf /" }, "risk": 3 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 5 }
    },
    {
      "id": "reference-pattern-002",
      "description": "/etc/passwd path escalates to risk 4",
      "category": "pattern-escalation",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "read", "parameters": { "path": "/etc/passwd" }, "risk": 2 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 4 }
    },
    {
      "id": "reference-pattern-003",
      "description": "DROP TABLE in SQL escalates to risk 5",
      "category": "pattern-escalation",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "query", "parameters": { "sql": "DROP TABLE users" }, "risk": 2 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 5 }
    },
    {
      "id": "reference-pattern-004",
      "description": "sudo in command escalates to risk 4",
      "category": "pattern-escalation",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "exec", "parameters": { "command": "sudo apt update" }, "risk": 2 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 4 }
    },
    {
      "id": "reference-pattern-005",
      "description": "Benign parameters produce no escalation",
      "category": "pattern-escalation",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "greet", "parameters": { "message": "hello world" }, "risk": 2 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 2 }
    },

    {
      "id": "reference-pattern-inv-001",
      "description": "High static risk not reduced by low pattern match",
      "category": "pattern-invariant",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "exec", "parameters": { "command": "ALTER TABLE x ADD col INT" }, "risk": 5 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 5 }
    },
    {
      "id": "reference-pattern-inv-002",
      "description": "No pattern match returns static risk unchanged",
      "category": "pattern-invariant",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "x", "parameters": { "msg": "safe content" }, "risk": 3 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 3 }
    },
    {
      "id": "reference-pattern-inv-003",
      "description": "Empty parameters returns static risk unchanged",
      "category": "pattern-invariant",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 2 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 2 }
    },

    {
      "id": "reference-pattern-kind-001",
      "description": "Kind-scoped pattern matches correct kind",
      "category": "pattern-kind-scoping",
      "config": {
        "rule_gate": { "threshold": 5 },
        "analyzer": {
          "type": "pattern",
          "include_defaults": false,
          "extra_patterns": [
            { "pattern": "\\bDROP\\b", "risk_level": 5, "description": "SQL drop", "kinds": ["database_query"] }
          ]
        }
      },
      "action": { "kind": "database_query", "name": "q", "parameters": { "sql": "DROP TABLE x" }, "risk": 1 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 5 }
    },
    {
      "id": "reference-pattern-kind-002",
      "description": "Kind-scoped pattern skipped for wrong kind",
      "category": "pattern-kind-scoping",
      "config": {
        "rule_gate": { "threshold": 5 },
        "analyzer": {
          "type": "pattern",
          "include_defaults": false,
          "extra_patterns": [
            { "pattern": "\\bDROP\\b", "risk_level": 5, "description": "SQL drop", "kinds": ["database_query"] }
          ]
        }
      },
      "action": { "kind": "tool_call", "name": "x", "parameters": { "cmd": "DROP TABLE x" }, "risk": 1 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 1 }
    },
    {
      "id": "reference-pattern-kind-003",
      "description": "Null kinds matches all action kinds",
      "category": "pattern-kind-scoping",
      "config": {
        "rule_gate": { "threshold": 5 },
        "analyzer": {
          "type": "pattern",
          "include_defaults": false,
          "extra_patterns": [
            { "pattern": "\\bDANGER\\b", "risk_level": 5, "description": "Danger keyword", "kinds": null }
          ]
        }
      },
      "action": { "kind": "anything", "name": "x", "parameters": { "x": "DANGER" }, "risk": 1 },
      "utility": null,
      "expected": { "decision": "allowed", "risk_score_level": 5 }
    },

    {
      "id": "reference-utility-001",
      "description": "No utility provided returns rule result unchanged",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": null,
      "expected": { "decision": "allowed" }
    },
    {
      "id": "reference-utility-002",
      "description": "Denied stays denied even with high utility",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5, "denied": ["x"] }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 1 },
      "utility": { "level": 5, "reasoning": "Maximum utility" },
      "expected": { "decision": "denied" }
    },
    {
      "id": "reference-utility-003",
      "description": "Equal risk and utility produces no escalation",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 3, "reasoning": "Matched" },
      "expected": { "decision": "allowed" }
    },
    {
      "id": "reference-utility-004",
      "description": "Utility exceeding risk produces no escalation",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 2 },
      "utility": { "level": 4, "reasoning": "High utility" },
      "expected": { "decision": "allowed" }
    },
    {
      "id": "reference-utility-005",
      "description": "Gap of 1 escalates allowed to needs_approval",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 3 },
      "utility": { "level": 2, "reasoning": "Low utility" },
      "expected": { "decision": "needs_approval" }
    },
    {
      "id": "reference-utility-006",
      "description": "Gap of 2+ clamped at 1 step: allowed escalates to needs_approval only",
      "category": "risk-utility-formula",
      "config": { "rule_gate": { "threshold": 5 }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "x", "parameters": {}, "risk": 5 },
      "utility": { "level": 1, "reasoning": "Minimal utility" },
      "expected": { "decision": "needs_approval" }
    },

    {
      "id": "reference-pipeline-001",
      "description": "Denied action short-circuits before analyzer runs",
      "category": "full-pipeline",
      "config": { "rule_gate": { "threshold": 5, "denied": ["dangerous"] }, "analyzer": { "type": "pattern", "include_defaults": true }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "dangerous", "parameters": { "command": "safe content" }, "risk": 1 },
      "utility": null,
      "expected": { "decision": "denied" }
    },
    {
      "id": "reference-pipeline-002",
      "description": "Pattern escalates risk but utility justifies it — stays at rule gate output",
      "category": "full-pipeline",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "exec", "parameters": { "command": "sudo apt update" }, "risk": 2 },
      "utility": { "level": 4, "reasoning": "User requested" },
      "expected": { "decision": "allowed", "risk_score_level": 4 }
    },
    {
      "id": "reference-pipeline-003",
      "description": "Allowed action passes through all three layers untouched",
      "category": "full-pipeline",
      "config": { "rule_gate": { "threshold": 5 }, "analyzer": { "type": "pattern", "include_defaults": true }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "greet", "parameters": { "message": "hello" }, "risk": 1 },
      "utility": { "level": 3, "reasoning": "Normal" },
      "expected": { "decision": "allowed", "risk_score_level": 1 }
    },
    {
      "id": "reference-pipeline-004",
      "description": "Above-threshold action with no utility gets needs_approval from rule gate",
      "category": "full-pipeline",
      "config": { "rule_gate": { "threshold": 2 }, "analyzer": { "type": "pattern", "include_defaults": true }, "action_gate": { "type": "risk_utility" } },
      "action": { "kind": "tool_call", "name": "write", "parameters": { "content": "safe data" }, "risk": 3 },
      "utility": null,
      "expected": { "decision": "needs_approval", "risk_score_level": 3 }
    }
  ]
}
```

- [ ] **Step 2: Validate JSON is well-formed**

Run: `python3 -c "import json; d = json.load(open('conformance/reference.json')); print(f'{len(d[\"vectors\"])} vectors loaded')"`

Expected: `21 vectors loaded`

- [ ] **Step 3: Verify all vector IDs are unique**

Run: `python3 -c "import json; d = json.load(open('conformance/reference.json')); ids = [v['id'] for v in d['vectors']]; dupes = [i for i in ids if ids.count(i) > 1]; print('OK' if not dupes else f'Duplicates: {set(dupes)}')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add conformance/reference.json
git commit -m "feat: add reference-tier conformance vectors (21 cases)

Covers: pattern-escalation, pattern-invariant, pattern-kind-scoping,
risk-utility-formula, full-pipeline"
```

---

### Task 6: Final validation

- [ ] **Step 1: Verify total vector count**

Run: `python3 -c "import json; p = json.load(open('conformance/protocol.json')); r = json.load(open('conformance/reference.json')); print(f'Protocol: {len(p[\"vectors\"])}, Reference: {len(r[\"vectors\"])}, Total: {len(p[\"vectors\"]) + len(r[\"vectors\"])}')" `

Expected: `Protocol: 30, Reference: 21, Total: 51`

- [ ] **Step 2: Verify all IDs are globally unique across both files**

Run: `python3 -c "import json; p = json.load(open('conformance/protocol.json')); r = json.load(open('conformance/reference.json')); ids = [v['id'] for v in p['vectors'] + r['vectors']]; dupes = [i for i in ids if ids.count(i) > 1]; print('OK — all 51 IDs unique' if not dupes else f'Duplicates: {set(dupes)}')"`

Expected: `OK — all 51 IDs unique`

- [ ] **Step 3: Run the full test suite to confirm nothing is broken**

Run: `uv run pytest -v`

Expected: All existing tests pass.

- [ ] **Step 4: Run lint**

Run: `uv run ruff check src/ tests/`

Expected: No errors.
