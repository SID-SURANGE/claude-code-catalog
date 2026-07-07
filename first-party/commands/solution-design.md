---
name: solution-design
description: End-to-end solution design for AI systems — staged interview, web-verified research, HLD with Mermaid diagrams, adversarial review, LLD, ADRs, and an optional confirm-gated repo scaffold. Run with the project description as the argument, or it will ask.
---

You are running an end-to-end solution-design pipeline for an AI architect.
Execute the seven stages below **in order**. Do not skip a stage; do not merge
stages; announce each stage in one line as you enter it. The user is the
architect — your job is to force rigor, verify facts, and produce artifacts,
not to replace their judgment.

Two hard rules that apply to every stage:

1. **No unstated assumptions.** Anything the design depends on is either asked
   in the interview or written into the decision log tagged `ASSUMED` with the
   default you chose. An `ASSUMED` entry must be visible in the final docs.
2. **No facts from memory.** Model names/IDs, pricing, rate limits, service
   quotas, regional availability, and context-window sizes MUST come from a
   web search performed now, recorded as `verified: <fact> (<source>, <date>)`.
   If you cannot verify a load-bearing fact, say so in the ADR and mark the
   decision provisional.

---

## Stage 0 — Intake

Take the project description from the command argument; if absent, ask for it
in one question. Then look around: if the current directory is an existing
project (README, manifests, source code), read enough to understand it and
treat this as **brownfield** — inherited constraints (stack, cloud, data
stores, team conventions) go straight into the decision log as constraints,
not questions. Greenfield otherwise. State which mode you're in.

## Stage 1 — Interview

At most **3 rounds** of batched questions (use the structured question tool if
available, otherwise numbered lists). Every question comes with a recommended
default so the user can answer fast. Every answer — and every default the user
accepts — becomes a numbered entry in the decision log. Do not ask what Stage 0
already established.

**Round 1 — Business frame:**
- Who uses it, expected scale (DAU, peak RPS), and growth over 12 months?
- Latency target (p50/p95) and availability expectation?
- Monthly budget ceiling (infra + model spend separately if possible)?
- Team: size, strongest skills, ops maturity (who gets paged at 3am)?
- Timeline to first production traffic?
- Compliance: PII? HIPAA/GDPR/SOC2? Data-residency regions?
- Build-vs-buy bias: prefer managed services or own the stack?

**Round 2 — AI frame** (adapt to what the project actually is):
- The AI task, precisely: what goes in, what must come out, what does "good"
  mean, and what error rate is tolerable?
- Eval strategy: offline eval set? LLM-as-judge? human review loop? How will
  regressions be caught before users see them?
- Data: sources, volume, freshness requirements, and **rights to use it**?
- Walk the RAG vs fine-tune vs agentic decision tree out loud with the user —
  recommend based on their answers (data freshness → RAG; stable style/format
  transfer → fine-tune; multi-step tool work → agentic; often a hybrid). Never
  assume the approach they named first is the right one.
- Models: hosted API vs self-hosted? Provider preferences or prohibitions?
  Fallback model policy?
- Token cost ceiling per request or per user-month?
- Streaming or batch? Real-time UX or async jobs?
- Guardrails: input/output filtering, prompt-injection posture, and where a
  human must stay in the loop?

**Round 3 — System frame:**
- Cloud preference (or on-prem/hybrid) and existing accounts/landing zones?
- Existing infra/services to reuse (auth, data warehouse, queues, CI/CD)?
- SLOs the business will actually sign, and the growth scenario to design for
  (design for 10x current, not 1000x)?
- Anything explicitly out of scope for v1?

If the user answers vaguely, propose a concrete default and tag it `ASSUMED` —
do not re-ask a fourth time.

## Stage 2 — Verified research

Web-search ONLY what the design hinges on. Typical set: current model options
and pricing for the chosen provider(s); the managed services you intend to use
(vector store, embedding service, queue, gateway) — availability and limits in
the chosen cloud + region; quota/latency numbers that affect the scaling model.
Keep a running `verified:` list; these lines get copied into the ADRs. Five to
ten searches is normal; more means you're researching, not verifying.

## Stage 3 — High-level design → `design/ARCHITECTURE.md`

Write the HLD using the skeleton at the bottom of this command. It must
contain:
- **System context diagram** (Mermaid, C4-context style: users, external
  systems, the system boundary).
- **Container diagram** (Mermaid, C4-container style: every deployable unit,
  data stores, model endpoints, and the protocols between them).
- Component responsibility table — one row per container: what it owns, what
  it must never do.
- Data-flow narrative for the primary path and the highest-risk path.
- **The AI pipeline in full detail**: for RAG — ingestion → chunking/indexing
  → retrieval → reranking → generation → eval loop, with the eval loop drawn
  as a first-class component, not a footnote. For agentic — agent topology,
  tool inventory, termination and budget controls. For fine-tune — data prep,
  training cadence, rollout/rollback of model versions.
- Scaling model: what scales horizontally, what's the first bottleneck, what
  breaks at 10x.
- Failure modes and degradation: model provider outage, vector-store
  unavailability, poisoned/low-quality retrievals — what does the user see?
- Security and trust boundaries, including where untrusted content (user
  input, retrieved documents) meets the model — prompt-injection surface.
- Rough monthly cost table built strictly from Stage-2 verified numbers, with
  the token-spend line item shown separately.

## Stage 4 — Adversarial review (always runs)

Check `~/.claude/agents/` for these and spawn the ones present against the
draft HLD, in parallel:
- `architecture-critic` — over-engineering and best-practice challenge.
- `assumption-auditor` — extract the design's implicit premises.
- `llm-architect` and/or `cloud-architect` — deep-dive validation of the AI
  pipeline and cloud choices respectively.

For any of the first two that is missing, spawn a general-purpose subagent
with the fallback adversarial brief at the bottom of this command. Then
**revise the HLD** and append a "Review log" section: each criticism, and
whether it was accepted (what changed) or rejected (why — one honest
sentence). Do not silently ignore any criticism.

## Stage 5 — Low-level design → `design/LLD.md`

Depth rule: a mid-level engineer can start any component without a design
meeting. Per component (use the skeleton below):
- API contracts (endpoints/events, request/response schemas, error shapes).
- Data schemas: relational tables, and for the vector side — index type,
  dimensionality, metadata fields, filter strategy, refresh policy.
- Prompt architecture: system prompt responsibilities, context budget in
  tokens per section, truncation policy, template versioning.
- Model configuration: chosen model + fallback chain, params, timeout/retry
  policy, circuit breaker thresholds.
- Queues/events: names, payload schemas, DLQ policy, idempotency keys.
- Observability: traces across the AI pipeline, token/cost metrics per
  request, eval-score dashboards, retrieval-quality and drift alerts.
- Sizing: instance/replica counts for launch scale, from the Stage-1 numbers.

## Stage 6 — ADRs → `design/adr/`

One `NNN-short-title.md` per significant decision (the approach choice, model
choice, vector store, sync-vs-async spine, buy-vs-build calls, anything a
reviewer challenged in Stage 4). Use the embedded template. Every ADR that
rests on a Stage-2 fact carries the dated `verified:` line. Every `ASSUMED`
decision from the interview gets an ADR with status `provisional` and a
revisit trigger.

## Stage 7 — Repo scaffold (confirm-gated)

Propose the complete repository tree for the chosen stack — follow the
ecosystem's conventional layout (src/package layout for Python, workspace
conventions for TS, etc.), with `design/` inside it, per-module stub files,
and a README per top-level module stating its single responsibility. **Show
the tree and ask for explicit confirmation before creating anything.** On
confirm, create directories, stubs, and READMEs. On decline, leave the tree
description in `design/ARCHITECTURE.md` as an appendix.

Finish with a **Next steps** list ordered by risk: the riskiest `ASSUMED` or
`provisional` decision first, each with the cheapest spike that would settle
it.

---

## Embedded templates

### ADR template

```markdown
# NNN — <decision title>
Status: accepted | provisional
Date: <YYYY-MM-DD>

## Context
<the forces: requirements, constraints, and interview decisions (by number) that shaped this>

## Decision
<one paragraph, active voice>

## Alternatives rejected
- <alternative> — <the one honest reason it lost>

## Consequences
<what gets easier, what gets harder, what we're now committed to>

## Verified facts
- verified: <fact> (<source>, <YYYY-MM-DD>)

## Revisit trigger
<the measurable condition under which this decision should be re-opened>
```

### ARCHITECTURE.md skeleton

`# <Project> — Architecture` → `## Decision log` (numbered, `ASSUMED` tags
visible) → `## System context` (Mermaid) → `## Containers` (Mermaid +
responsibility table) → `## Data flows` → `## AI pipeline` → `## Scaling
model` → `## Failure modes & degradation` → `## Security & trust boundaries`
→ `## Cost estimate` → `## Review log` → `## Appendix: proposed repo tree`
(only if scaffold was declined).

### LLD.md skeleton

`# <Project> — Low-Level Design` → one `## <Component>` section per container
with subsections: `API`, `Data`, `Prompts & context budget` (AI components
only), `Model config` (AI components only), `Events`, `Observability`,
`Sizing`.

### Fallback adversarial brief (when critic agents are not installed)

> Attack this architecture document as a skeptical principal engineer. Find:
> (1) over-engineering — components that exist for imagined scale or résumé
> value; (2) under-engineering — single points of failure and missing
> degradation paths; (3) unvalidated premises — anything treated as true that
> nothing in the doc verifies; (4) AI-specific traps — eval loop missing or
> decorative, no token cost control, prompt-injection surface unhandled,
> retrieval quality unmeasured. Report only findings that would change the
> design, each with the concrete failure it causes. No praise, no summary.
