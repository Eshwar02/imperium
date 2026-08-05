# LangChain Agent Layer — Design

**Date:** 2026-07-30
**Status:** Phase 1 implemented; Phases 2–3 specified at a high level (each gets its own spec later).

## Problem

Imperium's multi-agent spine talks to five non-OpenAI providers (NVIDIA Nemotron,
Groq, Gemini, Cerebras, Mistral) through a hand-rolled `httpx` call in
`imperium/llm/client.py`. Per-agent routing (`llm/routing.py`) picks an ordered
provider chain and falls through on error. This works but has no streaming,
tool-calling, retries, token accounting, or tracing — all noted as TODOs in the
old `complete()` docstring. We want the agents to run on LangChain so those
capabilities come from the framework instead of bespoke code.

## Approach: three phases, each independently shippable

The spine keeps its shape — **agents → `complete(role, …)` → routing chain**,
orchestrated today by a `ThreadPoolExecutor` — while the internals move to
LangChain incrementally.

### Phase 1 — LLM layer (DONE)

Introduce `imperium/llm/factory.py` that builds a per-role LangChain runnable and
rewire `client.py` to use it, **keeping `complete()`'s signature identical** so no
agent code changes.

- **Providers → `ChatOpenAI`.** Each provider is reached via
  `ChatOpenAI(base_url=..., api_key=..., model=..., use_responses_api=False)`. The
  `base_url`/model come from the existing `providers.py` registry, unchanged.
  `use_responses_api=False` is required — `ChatOpenAI` defaults to the Responses
  API, which these gateways do not implement.
- **Routing → fallbacks.** `routing.py` is unchanged. `factory.build_runnable(role)`
  materialises the role's chain as models and composes them with
  `.with_fallbacks()` (primary → rest), reproducing the old fall-through. Single-
  provider roles return the bare model.
- **Missing keys skipped at build time.** Providers whose key is unset/`changeme`
  are dropped before invoke rather than left to fail. No usable provider → `RuntimeError`.
- **New capabilities.** `client.chat(role, messages)` (message-list API),
  `client.stream(role, messages)` (chunked text), and per-role token accounting
  (`get_token_usage` / `reset_token_usage`) from each `AIMessage.usage_metadata`.
  Retries are configured per model (`max_retries=2`) before fallthrough.

**Files:** `llm/factory.py` (new), `llm/client.py` (rewritten shim),
`tests/test_llm_factory.py`, `tests/test_llm_client.py`. Deps added to
`pyproject.toml`: `langchain`, `langchain-core`, `langchain-openai`.

### Phase 2 — Tool-using agents (future spec)

Migrate agents from one-shot `complete()` to `langchain.agents.create_agent` with
tools: RKB semantic search (`rkb/embeddings.search`), Neo4j call-graph queries,
and file read. Use `ModelFallbackMiddleware` for the per-role chain (the agent-loop
equivalent of `.with_fallbacks()`). Migrate agent-by-agent; the `BaseAgent.run(ctx)`
contract stays. This is where the `complete()` docstring's "RAG context injection"
TODO lands, as a retrieval tool.

### Phase 3 — LangGraph orchestration (future spec)

Replace the `ThreadPoolExecutor` in `orchestrator.py` with a LangGraph `StateGraph`
modelling the gated pipeline: analyze → **Gate A interrupt** → simulate → changeset
→ **Gate B interrupt** → docs/comprehension. Checkpointing turns the human gates
into durable interrupts instead of separate API round-trips.

## Component boundaries

| Unit | Purpose | Depends on |
|------|---------|-----------|
| `providers.py` | Provider registry: base_url + key/model attrs | `config` |
| `routing.py` | role → ordered provider chain | — |
| `factory.py` | build per-role `ChatOpenAI` chain + fallbacks | `providers`, `routing`, `langchain-openai` |
| `client.py` | public API: `complete`/`chat`/`stream` + token accounting | `factory`, `langchain-core` |
| agents | call `complete`/`chat` by role | `client` |

`factory.py` is the only unit that knows LangChain model construction; agents never
import LangChain directly, so Phase 2/3 changes stay contained.

## Testing

- `test_llm_factory.py` — construction only, no network: role→provider mapping,
  `use_responses_api=False`, single vs multi-provider (fallback) shape, missing-key
  skipping, no-provider `RuntimeError`, unknown-role `ValueError`.
- `test_llm_client.py` — stubbed runnable: message construction (system/user),
  text extraction, per-role token accumulation, provider-failure wrapping.

All 10 tests pass. Network-dependent behaviour (actual provider calls, fallback on
live 5xx) is intentionally out of scope for unit tests.

## Out of scope (YAGNI for Phase 1)

- Provider-specific packages (`langchain-groq`, etc.) — the generic `ChatOpenAI`
  path covers all five; revisit only if a provider's non-standard fields are needed.
- LangSmith tracing wiring — the seam exists; enabling is a config concern.
- Async client — agents run in threads today; add if/when Phase 3 needs it.
