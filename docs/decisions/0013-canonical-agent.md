# ADR 0013 — The Python ReAct agent is the canonical agent

- **Status:** Accepted
- **Date:** 2026-06-03
- **Ticket:** [0025](../../tickets/active/0025-reconcile-two-agent-implementations.md)

## Context

The repo shipped two agent implementations:

1. `apps/agent/` — Python FastAPI ReAct loop with a real LLM planner
   (`plan_next_step`), the 4 verbs (READ-WEB / EXECUTE / VERIFY /
   PERSIST), and structured output. This is what the README,
   `docs/architecture.md`, and the pitch describe.
2. `apps/web/src/lib/agent-orchestrator.ts` — a scripted TypeScript
   pipeline with hardcoded `sleep()` pacing and a fixed 5-step sequence.
   **No LLM planner** — it is demo theater.

The live `/api/run` and `/api/stream` routes ran the **scripted TS
pipeline**, not the real agent. The Python service was effectively dead
on the live path.

## Decision

**`apps/agent/` (the Python ReAct loop) is the canonical agent.** It is
the implementation that matches the product promise ("an autonomous
agent that acts"), and the planner already exists.

- `/api/run` and `/api/stream` will route to the Python agent (via the
  existing `next.config.ts` rewrite `/api/agent/:path*` → `AGENT_BASE_URL`,
  or a server-side proxy).
- `agent-orchestrator.ts` is **demo-only**, gated behind
  `DEMO_FIXTURE_MODE`, and slated for deletion once the proxy path is
  proven. It must not gain new features.
- README + `docs/architecture.md` already describe the Python agent;
  they become accurate once the swap lands.

## Consequences / implementation order

The swap is an epic, sequenced through dependent tickets:

1. **[0027] durable job queue** — the agent must run work durably, not
   `asyncio.create_task` fire-and-forget.
2. **[0028] durable run/SSE state** — replace `_RUN_QUEUES` /
   `globalThis.__agentRuns` with InsForge-backed state + real pub/sub.
3. **[0029] real document extraction** — the agent must read the
   uploaded PDF, not replay fixtures.
4. **[0026] remove theatrical pacing** — delete the scripted pipeline's
   `sleep()` calls (or delete the file outright).
5. **[0014] prompt-injection mitigation** and **[0021] tracing** now
   target the Python loop.

Until the proxy path is integration-tested (needs both services
running), the scripted orchestrator stays as the `DEMO_FIXTURE_MODE`
fallback so the demo keeps working. The default run path flips to the
Python agent behind a `USE_PYTHON_AGENT` flag during migration, then
becomes unconditional.
