# Backend (Control Plane + Host Manager)

## Setup

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync
```

Copy the shared app template when starting locally:

```bash
cp .env.example .env
```

## Run Control Plane API

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run Host Manager Locally

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn host_manager.main:app --reload --host 0.0.0.0 --port 8787
```

## Local Postgres (recommended for migrations)

```bash
./scripts/db-up.sh
```

Default local URL:

```text
postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra
```

You can override with `POSTGRES_URL` (or `DATABASE_URL`).

## Migrations

Create migration:

```bash
./scripts/migrate-create.sh "describe change"
```

Upgrade:

```bash
./scripts/migrate-upgrade.sh
```

Downgrade one step:

```bash
./scripts/migrate-downgrade.sh
```

Downgrade to a specific revision:

```bash
./scripts/migrate-downgrade.sh <revision>
```

## Layout

- `app/`: main backend control plane
- `host_manager/`: Firecracker manager that runs on the GCP host VM
- `scripts/runtime/`: provisioning and deployment scripts for runtime infrastructure

## Runtime Env

Common local/dev settings live in `.env.example`.

For the GCP host manager, use `.env.host_manager.example` as the starting point. The important variables are:

- `GCP_PROJECT_ID`
- `GCP_COMPUTE_ZONE`
- `GCP_RUNTIME_HOST_INSTANCE_NAME`
- `SUTRA_RUNTIME_API_KEY`
- `AGENT_DISK_SIZE_GB`
- `AGENT_DISK_TYPE`
- `DEVICE_WAIT_TIMEOUT_S`
- `GUEST_API_PORT`

## Runtime Notes

- One persistent disk is created per agent, with a stable GCP-safe name: `agent-<uuid>`.
- The host manager now persists per-agent runtime metadata under `AGENTS_DIR/<agent_id>/runtime.json`, so a host-manager restart can still reconcile running Firecracker processes.
- The rootfs builder installs a guest-init script plus systemd units to mount `/dev/vdb`, wire `/home/user/.hermes` and `/home/user/workspace`, and auto-start Hermes.
- GCP nested virtualization must be allowed by org policy. If `compute.disableNestedVirtualization` is enforced, Firecracker cannot work because `/dev/kvm` will never appear.

## Runtime GCP Flow

Preflight or diagnose nested virtualization:

```bash
./scripts/runtime/check_nested_virtualization.sh
```

Provision the host:

```bash
./scripts/runtime/provision_gcp_host.sh
```

You can choose the documented fallback that uses the `enable-vmx` license-backed custom image:

```bash
GCP_NESTED_VIRT_MODE=license ./scripts/runtime/provision_gcp_host.sh
```

The provisioning script also prepares IAP SSH access for projects that block external IPs.

Smoke test the deployed host manager:

```bash
./scripts/runtime/smoke_test_host_manager.sh
```
