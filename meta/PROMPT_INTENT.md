# Prompt Intent

## Multi-Tenant Agent Runtime Mental Model

The proposed runtime model separates persistent agent state from disposable execution sandboxes:

- User and agent workspaces live in durable network-backed storage, mounted once at the host layer.
- Raw VMs act as latency-sensitive host nodes so the system can avoid slow cloud control-plane storage attachment paths during tool execution.
- A host-local orchestrator maintains a warm pool of anonymous, pre-booted isolated sandboxes.
- Each tool invocation claims a clean sandbox, attaches only the relevant agent workspace, runs with reduced privileges, then destroys the sandbox.
- The design goal is low-latency tool startup, strong tenant isolation, minimal cross-run state drift, and persistent user-controlled state independent of compute lifecycle.

Key tension to evaluate: the design optimizes for fast ephemeral execution, but it must still preserve the product’s sovereignty and safety constraints: tenant workspaces cannot leak across boundaries, cloud infrastructure must remain replaceable, and the system must be operable enough for non-technical users.

```mermaid
flowchart TB
%% Styling
classDef external fill:#f9f9f9,stroke:#333,stroke-width:2px;
classDef orchestrator fill:#d4edda,stroke:#28a745,stroke-width:2px;
classDef storage fill:#fff3cd,stroke:#ffc107,stroke-width:2px;
classDef compute fill:#cce5ff,stroke:#007bff,stroke-width:2px;
classDef os fill:#e2e3e5,stroke:#6c757d,stroke-width:2px;

    subgraph External ["External Services"]
        LLM["LLM API\n(Stateless generation)"]:::external
    end

    subgraph Storage ["Storage Layer"]
        NFS[("Managed Network File System\n(e.g., EFS, Cloud Filestore)")]:::storage
        AgentDir[/"/nfs/agents/agent_xyz\n(User State)"/]:::storage
        NFS --- AgentDir
    end

    subgraph HostVM ["Raw Virtual Machine (Host Node)"]
        HostKernel{"Host Linux Kernel"}:::os

        subgraph Core ["Orchestration Layer"]
            Orchestrator["Core Service (run_agent.py)\nEvent Loop & Context Manager"]:::orchestrator
        end

        subgraph ComputeBoundary ["Execution Layer (gVisor User-Space Kernels)"]
            WarmPool[["Warm Pool\n(Anonymous, Pre-booted)"]]:::compute
            ActiveSandbox[["Active Sandbox\n(Running Tool as 'uid 1000')"]]:::compute
            Destroyed(("Purged\nContainer")):::os
        end

        %% Host to Storage networking
        HostKernel ==== |"1. Persistent Network Connection"| NFS

        %% Execution Flow
        LLM -- "2. Emits JSON Tool Call" --> Orchestrator
        Orchestrator -- "3. Pauses LLM, Claims Container" --> WarmPool
        WarmPool -- "Transitions to" --> ActiveSandbox

        %% The Bind Mount
        HostKernel -- "4. Local Bind Mount ( < 5ms )" --> ActiveSandbox
        ActiveSandbox -. "Mount maps to: /workspace" .- AgentDir

        %% Results & Teardown
        ActiveSandbox -- "5. I/O Operations" --> AgentDir
        ActiveSandbox -- "6. Returns stdout/stderr/exit code" --> Orchestrator
        ActiveSandbox -- "7. Terminated Immediately" --> Destroyed

        %% Replenish & Resume
        Orchestrator -. "8. Boots Replacement in Background" .-> WarmPool
        Orchestrator -- "9. Injects stdout to context, resumes LLM" --> LLM
    end
```
