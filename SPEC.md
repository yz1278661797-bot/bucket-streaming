# Bucket Streaming Specification v1.0

## 1. Overview

Bucket Streaming is a context scheduling protocol for LLM-based agent skills with linear (or mostly-linear) multi-step pipelines. It defines:

- How a skill's source files are partitioned into **buckets**
- How buckets are **loaded, prefetched, and released** across conversation turns
- How the scheduler maintains **state** across turns
- How **jump-back** (user-initiated rollback) is handled

The protocol is **agent-agnostic** — it works with any LLM agent that can read files and follow state-tracking conventions.

---

## 2. Terminology

| Term | Definition |
|---|---|
| **Bucket** | A single file containing merged skill modules for a contiguous flow segment. One bucket ≈ one atomic read operation. |
| **Resident Layer** | Shared context that never leaves — flow definitions, global rules, forbidden-word lists. Never counted as a bucket. |
| **Active** | The bucket currently being executed. The agent reads from this bucket's instructions. |
| **Prefetch** | The next bucket, loaded immediately after the current bucket activates. Already in context before the user's next turn. |
| **Release** | The previous bucket, which the agent stops referencing. Tokens remain physically in context until displaced. |
| **State Tag** | A structured annotation in every agent response that tracks bucket position. |
| **Jump-Back** | User-initiated rollback to a previous step anchor point. |

---

## 3. Bucket Design Rules

### 3.1 Size Constraint

| Rule | Value |
|---|---|
| Maximum single-bucket size | 18,000 tokens (~32,000 characters for mixed Chinese/English) |
| Soft ceiling (offset fallback) | 25,000 tokens |
| Hard ceiling (must split) | 30,000 tokens |

**Rationale**: LLM `Read` tools typically have a ~20K token soft limit per call. Staying under 18K guarantees atomic reading. Buckets between 18K-25K may need offset-based chunked reads — acceptable but adds friction.

### 3.2 Split Point Rules

Buckets must be split at **semantic flow boundaries**, not arbitrary byte positions:

- ✅ Split at step transitions (end of step N → start of step N+1)
- ✅ Split at user interaction points (where the pipeline naturally pauses)
- ✅ Split at methodology transitions (e.g., "research phase" → "creative phase")
- ❌ Split mid-step
- ❌ Split inside a continuous instruction block
- ❌ Split at arbitrary byte offsets

### 3.3 Merging Rules

When multiple source files belong to the same flow segment, merge them into a single bucket file:

```
<!-- Bucket header with self-check -->
[Source module 1: full content]
[Source module 2: full content]
[Template file: full content]
[Judge personality: full content]
```

**Self-check header** (required, first 3 lines of every bucket file):

```
<!-- Bucket Streaming v1.0 -->
<!-- File: bucket-X-description.md -->
<!-- SELF-CHECK: If you see this line without upstream bucket output, STOP and request upstream. -->
```

This prevents the most common silent failure: the agent reading a bucket before its prerequisites are ready.

---

## 4. State Tracking Protocol

### 4.1 State Tag Format

Every agent response **must** begin with:

```
<bs-state: bucket=[ID], step=[STEP], prefetched=[ID|none], released=[ID|none]>
```

### 4.2 Fields

| Field | Required | Values | Description |
|---|---|---|---|
| `bucket` | Yes | A, B1, B2, C, D1, D2, E, ... | Current active bucket ID |
| `step` | Yes | Free text matching flow definition | Current step name from flow.yaml |
| `prefetched` | Yes | Bucket ID or `none` | Next bucket already in context |
| `released` | Yes | Bucket ID or `none` | Previous bucket evicted |

### 4.3 State Transitions

```
START
  │
  ▼
[Resident Layer loaded] ──→ [Bucket A prefetched]
  │                              │
  ▼                              ▼
<bs-state: bucket=A, ...>   [Bucket B1 prefetched]
  │
  ▼
[Step complete] ──→ Release A ──→ Activate B1 ──→ Prefetch B2
  │
  ▼
<bs-state: bucket=B1, ...>
  │
  ...
  │
  ▼
[Final bucket] ──→ Release previous ──→ prefetched=none
  │
  ▼
END
```

### 4.4 Enforcement

The state tag is a **soft constraint** — the agent is instructed to include it, but there is no runtime enforcement. The self-check header in each bucket file serves as the hard backup: if the agent reads a bucket without its prerequisites, the header text explicitly tells it to stop.

---

## 5. Prefetch and Release Rules

### 5.1 Prefetch

| Rule | Description |
|---|---|
| **When** | Immediately after the current bucket is activated — before any user interaction |
| **What** | Read the next bucket file in full |
| **Exception** | If current bucket is the final bucket → `prefetched=none` |
| **Fallback** | If bucket file >20K tokens → read with offset to complete |

### 5.2 Release

| Rule | Description |
|---|---|
| **When** | When transitioning from bucket N to bucket N+1 |
| **What** | Stop referencing bucket N's content. Do not re-read it unless the user initiates a jump-back. |
| **Mechanism** | Soft — the agent simply stops citing the released bucket. Physical token eviction depends on the LLM engine. |

### 5.3 Bucket Lifecycle Table

| Phase | Active | Prefetch | Release |
|---|---|---|---|
| Startup | — | Bucket A | None |
| Step 0-N | Bucket A | Bucket B1 | None |
| Step N+1-M | Bucket B1 | Bucket B2 | Bucket A |
| Step M+1-P | Bucket B2 | Bucket C | Bucket B1 |
| ... | ... | ... | ... |
| Final | Bucket Z | None | Bucket Y |

---

## 6. Jump-Back Protocol

### 6.1 Jump-Back Matrix

For each user-initiated rollback target, define:

| Field | Description |
|---|---|
| **Anchor** | Human-readable name (e.g., "Brand Constitution") |
| **Command** | User-facing trigger phrase (e.g., "jump back to constitution") |
| **Keep buckets** | Buckets whose output is preserved |
| **Release buckets** | Buckets whose output is discarded |
| **Re-inject** | Bucket to re-read (may be ~0 cost if cached) |

### 6.2 Within-Bucket Jump

If the jump target is in the same bucket as the current step:
- Re-reading cost: **~0 tokens** (Prompt Caching hit)
- Re-execute: from target step forward within the bucket

### 6.3 Cross-Bucket Jump

If the jump target is in a released bucket:
- Re-reading cost: **~target bucket token size**
- Release all buckets downstream of the target
- Re-inject the target bucket

### 6.4 Anti-Loop Rule

Maximum 2 jumps to the same anchor per session. On the 3rd attempt, the agent must respond:
> "Jumped back to this anchor twice already. Complete the current version and adjust in the next run."

---

## 7. Tool Compatibility

### 7.1 Read Tool Fallback

| Bucket Size | Read Strategy |
|---|---|
| <18K tokens | Single `Read` call — atomic |
| 18K-25K tokens | Single `Read` call (may warn); verify completeness |
| >25K tokens | `Read` with `offset` parameter to complete |

### 7.2 Prompt Caching Assumption

The protocol assumes the LLM platform supports **Prompt Caching** (e.g., Anthropic Claude, OpenAI with cache control). Without caching, bucket re-reads incur full token cost. With caching, within-session bucket re-reads approach zero cost.

---

## 8. Implementation Checklist

To convert an existing skill to Bucket Streaming:

- [ ] 1. Map the full flow — list every step and its source file
- [ ] 2. Measure token sizes for all source files
- [ ] 3. Group steps into buckets (3-8 steps each, <18K tokens each)
- [ ] 4. Split oversized files at semantic boundaries
- [ ] 5. Merge source files into bucket files with self-check headers
- [ ] 6. Add the bucket lifecycle table to the main SKILL.md
- [ ] 7. Add the `<bs-state>` tag specification
- [ ] 8. Add the jump-back matrix
- [ ] 9. Keep original source files as safety net (do not delete)
- [ ] 10. Run a full pipeline test and verify all steps execute correctly

---

## 9. Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-06-27 | Initial specification. |
