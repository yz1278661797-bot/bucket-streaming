# Bucket Streaming Template

> Copy-paste this into your skill's `SKILL.md`. Replace placeholders with your bucket IDs, step names, and file paths.

---

## Bucket Scheduling State Machine

### Resident Layer

Always in context. Never released.

Read at startup:
- `config/flow.yaml` — full flow definition
- `config/global-rules.md` — shared constraints

---

### Bucket Lifecycle Table

| Phase | Active Bucket | Prefetch (inject now) | Release (evict) |
|---|---|---|---|
| **Startup** | Resident Layer | Bucket A | None |
| **Phase 1** | Bucket A | Bucket B | None (first bucket) |
| **Phase 2** | Bucket B | Bucket C | Bucket A |
| **Phase 3** | Bucket C | Bucket D | Bucket B |
| **Phase 4** | Bucket D | None (final) | Bucket C |

*(Extend rows to match your flow.)*

---

### Bucket File Map

| Bucket | File | ~Tokens | Description |
|---|---|---|---|
| A | `buckets/bucket-A-xxx.md` | ~X,XXX | Steps 1-3: activation, setup |
| B | `buckets/bucket-B-xxx.md` | ~X,XXX | Steps 4-7: core processing |
| C | `buckets/bucket-C-xxx.md` | ~X,XXX | Steps 8-10: output generation |
| D | `buckets/bucket-D-xxx.md` | ~X,XXX | Steps 11-13: delivery |

---

### State Tracking Tag (MANDATORY)

**Every response must begin with:**

```
<bs-state: bucket=[ID], step=[STEP_NAME], prefetched=[ID|none], released=[ID|none]>
```

**Example:**
```
<bs-state: bucket=B, step=summarize, prefetched=C, released=A>
```

**Rules:**
- `bucket`: Current active bucket (A, B, C, D, ...)
- `step`: Current step name from flow.yaml
- `prefetched`: Next bucket already loaded into context, or `none`
- `released`: Previous bucket evicted from attention, or `none`
- Update every turn — even if step hasn't advanced, the tag must still appear

---

### Bucket Inject Instruction

**When injecting a bucket for the first time:**
1. Read the bucket file in full: `buckets/bucket-X-xxx.md`
2. If truncated (>20K tokens), use `offset` to read the remainder
3. Verify the self-check header: `<!-- SELF-CHECK: ... -->`
4. Begin executing the first step in this bucket

---

### Jump-Back Matrix

| Anchor | Command | Keep | Release | Re-inject | Cost |
|---|---|---|---|---|---|
| Phase 1 restart | "go back to setup" | Resident | B, C, D | Bucket A | ~X,XXX tokens |
| Phase 2 restart | "go back to process" | Resident, A, B | C, D | Bucket B | ~0 (cached) |
| Phase 3 restart | "go back to output" | Resident, A, B, C | D | Bucket C | ~0 (cached) |

**Rules:**
- Within-bucket jump → ~0 tokens (Prompt Caching hit)
- Cross-bucket jump (target released) → re-read target bucket
- Max 2 jumps to same anchor per session

---

### Jump-Back Prompt (auto-appended to every response)

```
[Jump options: go back to setup | go back to process | go back to output]
```

---

### Bucket Self-Check Header

Every bucket file must begin with these exact 3 lines:

```
<!-- Bucket Streaming v1.0 -->
<!-- File: bucket-X-description.md -->
<!-- SELF-CHECK: If you see this line without upstream bucket output, STOP and request upstream. -->
```

---

### Read Fallback for Large Buckets

Buckets exceeding 20K tokens may trigger Read tool truncation. This is normal.
Use offset reads to complete:

```
# If bucket-A reads 500 lines and stops with truncation warning:
Read bucket-A-xxx.md offset=500 limit=500
```

---

## File Structure

```
your-skill/
├── SKILL.md                 ← Main entry with this scheduler
├── buckets/                 ← Merged bucket files
│   ├── bucket-A-xxx.md
│   ├── bucket-B-xxx.md
│   ├── bucket-C-xxx.md
│   └── bucket-D-xxx.md
├── modules/                 ← Original source files (keep as safety net)
│   ├── module_1.md
│   ├── module_2.md
│   └── ...
├── config/
│   ├── flow.yaml            ← Resident layer
│   └── global-rules.md       ← Resident layer
└── templates/               ← Original templates (keep as safety net)
    └── ...
```
