# Deprioritized Work

This file tracks deliberate deferrals. These are not rejected ideas; they are parked so the current implementation can stay small while we keep the pi-mono direction visible.

## Agent Runtime

- Durable `AgentEvent` persistence is deferred. We currently stream runtime events to clients and persist the canonical `AgentMessage[]` transcript on the session.
- Strong custom message schemas are deferred. `CustomAgentMessage` is currently a permissive fallback so app-specific messages can pass through `transform_context` and `convert_to_llm`.
- Multi-agent orchestration is deferred. The current backend assumes one hydrated agent per session, with `User`, `Agent`, and `AgentSession` as the starting data model.
- Full tenant isolation is deferred. We removed active `tenant_id` from the request/data model for now and are modeling around `User` and `Agent`.

## AI Provider Layer

- A generated model catalog equivalent to pi-ai's `models.generated.ts` is deferred. For now, model metadata is supplied from config or stored agent state.
- The model registry helpers are deferred: `get_model`, `get_models`, `get_providers`, `calculate_cost`, `supports_xhigh`, and `models_are_equal`.
- Full provider adapter parity is deferred. `openai-completions` and `faux` are the practical paths today; most other APIs are placeholders until we implement their wire protocols.
- MiniMax provider execution is deferred even though `MINIMAX_API_KEY` exists in `backend/.env`. We should add it after the generated model catalog and Anthropic-compatible adapter exist; tests should mock provider calls when that path is introduced.
- Provider-specific compatibility handling is deferred beyond the current minimal `compat` field. This includes OpenAI Responses, Anthropic Messages, Bedrock, Google, Mistral, OAuth-backed providers, prompt caching, and provider-specific thinking/reasoning behavior.

## Product Surface

- Multi-tenant backend APIs are deferred until the single-user/session runtime is stable.
- Rich frontend agent controls are deferred. The current frontend should stay minimal and API-driven while backend runtime semantics settle.
- Generated frontend API client integration is started but not treated as the main product surface yet.

## Revisit Triggers

- Add the generated model catalog before serious multi-provider support.
- Add durable event storage before we need replay/debug timelines beyond the canonical message transcript.
- Add explicit custom message models when the frontend introduces real app-only message types such as notifications, artifacts, approvals, or status updates.
- Add tenant boundaries before any shared deployment or organization-level access control.
