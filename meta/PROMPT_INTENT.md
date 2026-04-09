# Prompt Intent

## Current Runtime Direction (2026-04-08)

The current design direction moves from host-managed microVM orchestration toward a split control-plane/execution-plane architecture:

- Tier 1 (Presentation): React UI behind Nginx.
- Tier 2 (Control Plane on GCP): FastAPI + Hermes orchestrator handles user sessions, context hydration, model calls, tool routing, and stream fanout.
- Tier 2 state: tenant profiles are persisted on GCP-backed disk (SQLite on Persistent Disk for now).
- Tier 3 (Execution Plane on Modal): per-task sandbox execution in Modal sandboxes, with workspace state on Modal Volumes.
- External model providers remain stateless LLM APIs (OpenRouter/Anthropic/etc.).

Primary intent:
- Keep orchestration and identity in Sutra control plane.
- Keep code execution isolated and disposable.
- Keep tenant state durable and scoped per profile.
- Stream live tool output and model output back to UI with minimal latency.

Key constraints to preserve while implementing:
- True multi-tenancy by default (no cross-tenant workspace exposure).
- Strong separation between long-lived orchestrator state and short-lived tool runtime.
- No hidden platform lock-in in core data model or API contracts.
- Non-technical-user usability: login and immediately usable web flow.

```mermaid
graph TD
    User((User))

    subgraph Tier_1 [Tier 1: Presentation Layer]
        React[React Frontend]
        Nginx[Nginx Reverse Proxy]
    end

    subgraph Tier_2 [Tier 2: Control Plane GCP]
        FastAPI[FastAPI / Hermes Orchestrator]

        subgraph State [State Management]
            PD[(GCP Persistent Disk)]
            P1[Profile: Tenant A]
            P2[Profile: Tenant B]
            PD --- P1
            PD --- P2
        end
    end

    subgraph Tier_3 [Tier 3: Execution Plane Modal]
        Sandbox[Modal Sandbox microVM]
        Volume[(Modal Volume workspace)]
    end

    subgraph External [External Services]
        LLM[LLM API OpenRouter/Anthropic]
    end

    User -- "1. HTTP POST (Prompt)" --> React
    React -- "2. Routes traffic" --> Nginx
    Nginx -- "3. Forward to Backend" --> FastAPI

    FastAPI -- "4. Hydrate context (SQLite)" --> P1
    FastAPI -- "5. Outbound prompt" --> LLM
    LLM -- "6. SSE JSON Tool Call" --> FastAPI

    FastAPI -- "7. API: Spawn & Execute" --> Sandbox
    Sandbox -- "8. Mounts" --> Volume

    Sandbox -- "9. Streams stdout/stderr" --> FastAPI
    FastAPI -- "10. SSE Stream to UI" --> React
    React -- "Renders live text" --> User

    classDef gcp fill:#e8f0fe,stroke:#4285f4,stroke-width:2px,color:#000;
    classDef modal fill:#f3f0ff,stroke:#8a2be2,stroke-width:2px,color:#000;
    classDef react fill:#e6ffff,stroke:#00d8ff,stroke-width:2px,color:#000;
    classDef db fill:#fdf6e3,stroke:#b58900,stroke-width:2px,color:#000;
    classDef external fill:#fce8e6,stroke:#ea4335,stroke-width:2px,color:#000;

    class Tier_2,FastAPI gcp;
    class Tier_3,Sandbox modal;
    class Tier_1,React,Nginx react;
    class PD,P1,P2,Volume db;
    class External,LLM external;
```
