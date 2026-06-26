# Data Analysis Pipeline · Bucket Streaming Demo

A minimal 4-step example demonstrating bucket streaming for LLM agent skills.

Pipeline: search → summarize → chart → export.

---

## Bucket Scheduling State Machine

### Resident Layer

Always in context:
- `config/flow.yaml` — flow definition

---

### Bucket Lifecycle Table

| Phase | Active | Prefetch | Release |
|---|---|---|---|
| Startup | Resident Layer | Bucket A | None |
| Search | Bucket A | Bucket B | None (first) |
| Summarize | Bucket B | Bucket C | Bucket A |
| Chart | Bucket C | Bucket D | Bucket B |
| Export | Bucket D | None (final) | Bucket C |

---

### Bucket File Map

| Bucket | File | ~Tokens | Contains |
|---|---|---|---|
| A | `buckets/bucket-A-search.md` | ~800 | Search strategy, query generation |
| B | `buckets/bucket-B-summarize.md` | ~900 | Data aggregation, insight extraction |
| C | `buckets/bucket-C-chart.md` | ~700 | Visualization types, chart config |
| D | `buckets/bucket-D-export.md` | ~500 | Export formats, delivery templates |

---

### State Tracking Tag (MANDATORY)

Every response must begin with:

```
<bs-state: bucket=[ID], step=[STEP], prefetched=[ID|none], released=[ID|none]>
```

---

### Jump-Back Matrix

| Anchor | Command | Keep | Release | Re-inject | Cost |
|---|---|---|---|---|---|
| Search | "redo search" | Resident | B, C, D | Bucket A | ~800 tokens |
| Summarize | "redo summary" | Resident, A, B | C, D | Bucket B | ~0 (cached) |
| Chart | "redo chart" | Resident, A, B, C | D | Bucket C | ~0 (cached) |

---

### Jump-Back Prompt (auto-appended)

```
[Jump options: redo search | redo summary | redo chart]
```

---

## Startup

1. Read `config/flow.yaml`
2. Output: `<bs-state: bucket=startup, step=init, prefetched=A, released=none>`
3. Read `buckets/bucket-A-search.md` (prefetch Bucket A)
4. Ask user for data analysis task
