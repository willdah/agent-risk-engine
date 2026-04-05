# Conformance Test Vectors — Design Spec

> **Note:** This spec predates the risk tolerance elevation — shipped config uses `risk_tolerance`/`kind_tolerances` instead of `threshold`/`kind_thresholds`, and category names use `tolerance-boundary`/`kind-tolerances` instead of `threshold-boundary`/`kind-thresholds`.

## Goal

Create a suite of JSON test vectors that define correct behavior for the Agent Risk Protocol and its reference implementation. The vectors serve two audiences:

1. **Other-language implementors** (Go, Rust, TypeScript) — protocol-tier vectors test universal semantics only
2. **Python users writing custom layers** — reference-tier vectors test PatternAnalyzer, RiskUtilityGate, and full pipeline behavior

The vectors are JSON-only. No executable runner is shipped — consumers parse and run them however they like.

## File Structure

```
conformance/
  README.md          — schema docs, usage instructions, tier descriptions
  protocol.json      — universal protocol semantics (~30 cases)
  reference.json     — reference implementation behavior (~21 cases)
```

## Vector Schema

Each JSON file is an object with a `version` string and a `vectors` array:

```json
{
  "version": "1.0.0",
  "description": "...",
  "vectors": [...]
}
```

Each vector:

```json
{
  "id": "protocol-rule-gate-001",
  "description": "Denied-set action is always denied regardless of risk level",
  "category": "denied-is-final",
  "config": {
    "rule_gate": {
      "threshold": 5,
      "denied": ["drop_database"]
    }
  },
  "action": {
    "kind": "tool_call",
    "name": "drop_database",
    "parameters": {},
    "risk": 1
  },
  "utility": null,
  "expected": {
    "decision": "denied"
  }
}
```

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique ID. Prefixed by tier (`protocol-` / `reference-`) and component, with sequence number. |
| `description` | string | Human-readable description of what the vector tests. |
| `category` | string | Groups related cases for reporting. |
| `config` | object | Evaluator configuration. See Config Schema below. |
| `action` | object | The Action envelope: `kind`, `name`, `parameters`, `risk`, `metadata`. |
| `utility` | object or null | `{"level": N, "reasoning": "..."}` or `null` when absent. |
| `expected` | object | Expected outcome. Protocol-tier: `{"decision": "..."}`. Reference-tier may add `{"decision": "...", "risk_score_level": N}`. |

### Config Schema

Protocol-tier vectors use only `rule_gate`:

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

All `rule_gate` fields except `threshold` are optional and default to their empty/false values.

Reference-tier vectors may additionally include:

```json
{
  "rule_gate": { ... },
  "analyzer": {
    "type": "pattern",
    "include_defaults": true,
    "extra_patterns": []
  },
  "action_gate": {
    "type": "risk_utility"
  }
}
```

Analyzer `type` values: `"passthrough"`, `"pattern"`. Action gate `type` values: `"passthrough"`, `"risk_utility"`.

## Protocol-Tier Categories (~30 vectors)

### 1. Denied is final (5 cases)

- Denied-set action denied regardless of low risk
- Denied-set overrides allowed-set (name in both)
- Denied-set overrides approve-set (name in both)
- Denied-set overrides all three sets
- Denied-set action denied even at full-trust threshold

### 2. Evaluation order (4 cases)

- Allowed-set bypasses threshold (risk 5 with threshold 1, still allowed)
- Allowed-set overrides approve-set
- Approve-set forces needs_approval even when threshold would allow
- Name not in any set falls through to threshold comparison

### 3. Threshold boundary (5 cases)

- Risk exactly at threshold: allowed
- Risk below threshold: allowed
- Risk above threshold, non-strict: needs_approval
- Risk above threshold, strict: denied
- Threshold 5 allows everything

### 4. Kind-scoped thresholds (4 cases)

- Kind threshold overrides default threshold
- Unknown kind falls back to default threshold
- Kind threshold with strict mode
- Name override takes precedence over kind threshold

### 5. Escalation only (4 cases)

- Layer 3 can escalate allowed to needs_approval
- Layer 3 can escalate allowed to denied
- Layer 3 can escalate needs_approval to denied
- Layer 3 cannot relax needs_approval to allowed

### 6. Secure by default (2 cases)

- Unknown action with risk 5 at default threshold (2): needs_approval
- Unknown action with risk 5 at default threshold, strict mode: denied

### 7. Utility constraints (6 cases)

These encode two normative constraints to be added to PROTOCOL.md:

**Constraint 1**: Utility MUST NOT reduce the effective decision by more than one escalation level relative to what risk alone would produce.

**Constraint 2**: Risk level 5 actions MUST NOT be resolved as `allowed` by utility alone.

Vectors:

- Utility cannot relax a denied result
- Utility cannot relax below rule gate output
- Risk 5 with utility 5: must not be allowed by utility alone
- Risk 4, utility 5: needs_approval at most (utility offsets by at most 1)
- Equal risk and utility: no escalation from utility
- Risk exceeds utility: escalation occurs

## Reference-Tier Categories (~21 vectors)

### 1. Pattern analyzer — escalation (5 cases)

- `rm -rf /` escalates to risk 5
- `/etc/passwd` path escalates to risk 4
- `DROP TABLE` escalates to risk 5
- `sudo` escalates to risk 4
- Benign parameters: no escalation

### 2. Pattern analyzer — escalation-only invariant (3 cases)

- High static risk not reduced by low pattern match
- No match returns static risk unchanged
- Empty parameters returns static risk unchanged

### 3. Pattern analyzer — kind scoping (3 cases)

- Kind-scoped pattern matches correct kind
- Kind-scoped pattern skipped for wrong kind
- Null kinds matches all kinds

### 4. RiskUtilityGate formula (6 cases)

- No utility: returns rule result unchanged
- Denied stays denied with high utility
- Equal risk and utility: no escalation
- Utility exceeds risk: no escalation
- Gap of 1: allowed escalates to needs_approval
- Gap of 2+: allowed escalates to needs_approval (clamped at 1 step after implementation change)

**Note**: The current `RiskUtilityGate` allows up to 2 escalation steps (`action_gate.py:66`, `steps = min(gap, 2)`). This must be changed to `min(gap, 1)` to match normative Constraint 1. The reference vectors will reflect the post-change behavior.

### 5. Full pipeline integration (4 cases)

- Denied short-circuits before analyzer runs
- Pattern match escalates risk, utility justifies it
- Allowed action through all three layers untouched
- Above-threshold action with no utility: needs_approval passed through

## Protocol Changes

Add two normative constraints to PROTOCOL.md Evaluation Semantics as items 6 and 7:

> 6. **Utility offset limit.** Utility MUST NOT reduce the effective decision by more than one escalation level relative to what risk alone would produce.
>
> 7. **Critical risk protection.** Risk level 5 actions MUST NOT be resolved as `allowed` by utility alone. Only explicit developer rules (allow lists) may auto-allow critical-risk actions.

## Implementation Change

`action_gate.py:66`: change `steps = min(gap, 2)` to `steps = min(gap, 1)` to enforce Constraint 1 in the reference implementation.

Corresponding test updates in `test_utility_gate.py`:

- `TestGapTwo.test_allowed_to_denied` changes expected result from `denied` to `needs_approval`
- `TestGapTwo.test_large_gap_clamps_at_denied` changes expected result from `denied` to `needs_approval`
- `TestGapTwo` class should be renamed to reflect new clamping behavior
