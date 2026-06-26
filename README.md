# Bucket Streaming · LLM Context Scheduling

> *"God of War loads the next area before you reach the door. Your LLM agent waits for the user to say 'continue' before reading the next module. This is wrong."*

**Bucket Streaming** is a context management pattern for multi-step LLM agent skills. Inspired by the bucket-streaming engine in *God of War* (2018, Santa Monica Studio), it replaces file-level lazy loading with predictive prefetch + soft eviction for linear pipelines.

---

## The Problem

Most LLM agent skills use **file-level lazy loading**: a routing table tells the agent "read file X when step N begins."

```
SKILL.md: "When executing module 3, read module_3.md"
SKILL.md: "When executing module 4, read module_4.md + storyboard.md + judges/a.md + judges/b.md + ..."
```

This works. But it has three failure modes:

1. **Re-read overhead.** The agent re-reads files it already loaded earlier in the conversation — old tokens get pushed out, new ones come in. Cumulative token cost grows linearly with steps.

2. **No jump-back support.** When the user says "go back to step 3," the agent has to re-read 5+ files. Context is already polluted with later-step artifacts.

3. **Attention pollution.** Module 0's forbidden-word list is still floating in context when the agent is executing module 6 — wasting attention budget on irrelevant constraints.

---

## The Pattern

Bucket Streaming replaces "read when you need it" with **"read before you need it, forget when you're done."**

```
┌─────────────────────────────────────────────────────────┐
│                   Resident Layer                         │
│  (always in context: flow.yaml, global rules)            │
├─────────────────────────────────────────────────────────┤
│  Bucket A    │  Bucket B    │  Bucket C    │  Bucket D   │
│  (active)    │  (prefetch)  │  (released)  │  (future)   │
│  READ NOW    │  READ NOW    │  EVICTED     │  untouched  │
└─────────────────────────────────────────────────────────┘
         ↑ current step          ↑ next step
```

### Core Rules

| Rule | Description |
|---|---|
| **Active** | The bucket for the current step is fully loaded and executing |
| **Prefetch** | The next bucket is loaded *immediately*, before the user's next turn |
| **Release** | The previous bucket is evicted — the agent stops referencing it |
| **Resident** | Shared context (flow definitions, global rules) never leaves |

### State Tracking

Every agent response carries a state tag:

```
<bs-state: bucket=B, step=summarize, prefetched=C, released=A>
```

This gives the scheduler persistent awareness of position, preventing the most common failure mode: "I forgot which bucket I'm in."

### Jump-Back Matrix

| Jump target | Keep buckets | Release buckets | Re-read cost |
|---|---|---|---|
| Within current bucket | All | None | ~0 tokens (cache hit) |
| Into prefetched bucket | All | None | ~0 tokens (already in context) |
| Into released bucket | Upstream | Downstream | Re-read target bucket |

---

## God of War Analogy (in detail)

Santa Monica Studio's 2018 *God of War* runs on a bucket-streaming engine. The PS4 has 8GB of RAM — not enough to hold an entire level. So the engine splits the world into buckets and loads them predictively:

| God of War (Decima Engine) | Bucket Streaming (LLM Skills) |
|---|---|
| World split into path-buckets (~50m each) | Skill split into flow-buckets (3-8 steps each) |
| Prefetch 2-3 buckets ahead based on camera + player position | Prefetch 1 bucket ahead based on current step + flow definition |
| Release buckets behind the player (background evict) | Release buckets after step completion (stop referencing) |
| SSD read for miss: loading screen | Prompt Cache hit for miss: ~0 token cost |
| PS4 8GB hard ceiling | Context window 128K+ (soft ceiling, forgiving) |

**Three advantages LLM-side that Decima doesn't have:**

1. **Jump-back is nearly free.** God of War needs a loading screen when the player turns back. Bucket Streaming hits Prompt Caching — zero-cost re-read.
2. **The ceiling is soft.** PS4 OOMs at 8GB. Context windows are generous — you won't hit the ceiling with 2-3 buckets.
3. **100% prediction accuracy.** The player *might* turn back. Your skill flow is *defined by you* — "search → summarize → chart" never changes unless the user explicitly says "go back."

---

## Quick Start

### 1. Analyze your skill

```bash
python tools/bucket-splitter.py /path/to/your/skill
```

Output:
```
modules/module_1.md ..... 12,340 chars  ~6,855 tokens
modules/module_2.md ..... 48,200 chars  ~26,777 tokens ⚠️ >20K
modules/module_3.md ..... 8,100 chars   ~4,500 tokens
templates/output.md ..... 11,200 chars  ~6,222 tokens
judges/reviewer_a.md .... 420 chars     ~233 tokens

--- Suggested split ---
Bucket B:  modules/module_2.md  →  SPLIT at line 820 (~15K tokens each)
  → bucket-B1.md  (~13,000 tokens)
  → bucket-B2.md  (~13,800 tokens)

--- Suggested buckets ---
Bucket A:  module_1.md                                ~6,855 tokens
Bucket B1: module_2.md [lines 1-820]                  ~13,000 tokens
Bucket B2: module_2.md [lines 821-end]                ~13,800 tokens
Bucket C:  module_3.md + output.md + reviewer_a.md    ~11,000 tokens
```

### 2. Create bucket files

Manually merge source files or use the splitter:

```bash
python tools/bucket-splitter.py /path/to/your/skill --merge
```

### 3. Add the scheduler to your SKILL.md

Copy the bucket scheduling state machine, state tag spec, and jump-back matrix from `TEMPLATE.md` into your skill's main entry file.

### 4. Run

Your agent will now prefetch the next bucket before each user turn, and soft-evict completed buckets.

---

## Specification

See [SPEC.md](SPEC.md) for the full protocol specification.

See [TEMPLATE.md](TEMPLATE.md) for a copy-paste-ready scheduler template.

See [example-data-analysis/](example-data-analysis/) for a minimal working example.

---

## Limitations

- **Soft eviction only.** LLM engines do not expose a context eviction API. "Release" means "the agent stops referencing this bucket" — the tokens remain physically in context until displaced by new ones. This is a platform limitation, not a design flaw.
- **Linear flows only.** If your skill needs random access to modules (e.g., "look up any section at any time"), use RAG-style retrieval instead.
- **Manual bucket design.** You must decide where to split. The splitter tool suggests boundaries but can't automatically determine semantic coherence.

---

## License

MIT
