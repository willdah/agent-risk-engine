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

Protocol-tier vectors primarily use `rule_gate`. Vectors testing Layer 3 escalation and utility constraints additionally include `action_gate`:

```json
{
  "rule_gate": {
    "risk_tolerance": 3,
    "strict": false,
    "allowed": [],
    "approve": [],
    "denied": [],
    "kind_tolerances": {}
  }
}
```

`risk_tolerance` (integer 1-5): actions with risk at or below this value are auto-allowed. Actions above require approval (or are denied in strict mode). All other fields are optional (default to empty/false).

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
- `evaluation-order` — denied > allowed > approve > risk tolerance
- `tolerance-boundary` — at/below/above risk tolerance behavior
- `kind-tolerances` — per-kind risk tolerance overrides
- `escalation-only` — later stages can only escalate
- `secure-by-default` — unknown actions default to highest risk
- `utility-constraints` — utility offset and critical risk limits

**Reference-tier:**
- `pattern-escalation` — PatternAnalyzer risk bumping
- `pattern-invariant` — escalation-only in analyzer
- `pattern-kind-scoping` — kind-filtered patterns
- `risk-utility-formula` — RiskUtilityGate behavior
- `full-pipeline` — end-to-end RiskEvaluator
