# Backend MVP Implementation Plan

## Scope

Implement the first backend slice for Phase 1:

1. authenticated user signs in
2. user record is created on first sighting
3. one agent is auto-created for a new user
4. user can create additional agents

This plan intentionally stops before chat execution, SSE streaming, and Modal terminal orchestration. Those come later.

---

## Confirmed Decisions

- Control-plane relational state is Postgres only.
- Dev and prod should use Neon URLs from env, not local SQLite.
- Each agent owns exactly one `hermes_home`.
- Only one top-level active session per agent is allowed for MVP.
- `hermes_home` lives on GCP NFS.
- `workspace` lives in Modal persistence and is separate from `hermes_home`.
- Hermes internal SQLite inside `hermes_home` is left alone for now.

This means we do **not** need an `AgentLease` table yet. Since we are not spinning shared workers up and down and we are explicitly allowing only one active top-level session per agent, lease coordination would be premature complexity.

---

## Hermes Ground Truth We Should Reuse

This backend should follow Hermes' existing profile model instead of inventing a parallel one.

Important Hermes behavior:

- Hermes profiles are just isolated `HERMES_HOME` directories.
- The active home is selected by setting `HERMES_HOME` **before imports**.
- Hermes already defines the bootstrap directory layout for a profile in `hermes-agent/hermes_cli/profiles.py`.
- Hermes already has a safe pattern for seeding bundled skills into a profile via subprocess in `seed_profile_skills(...)`.
- Hermes subagents are child sessions under the same home, not separate homes.

Implementation consequence:

- Our hosted "agent" should map directly to one Hermes-style profile root.
- Our code should prepare that profile root in a Hermes-compatible way.
- Any code that imports and runs Hermes must do so behind a small adapter boundary, with `HERMES_HOME` fixed before Hermes runtime imports.

---

## Minimal Data Model

Keep the data model small.

### `User`

- `id`
- `firebase_uid`
- `email`
- `name`
- timestamps / metadata from `ModelBase`

### `Agent`

- `id`
- `user_id`
- `name`
- `hermes_home_path`
- `workspace_key`
- timestamps / metadata from `ModelBase`

Notes:

- Do not add `is_default` right now.
  - The "default first agent" rule is a provisioning rule, not enduring product state.
  - If a user has exactly one agent on first login, that is enough.
- Do not add `workspace_provider`.
  - Modal is the only provider in this design.
- Do not add `status` yet.
  - Provisioning can fail fast and return an error. We do not need lifecycle state until there is background provisioning or retries.

### `AgentSandbox`

Do not expand this now. It is not needed for the signup + create-agent flow. Keep it out of the critical path unless later runtime work requires it.

---

## Environment Contract

Backend settings should resolve Postgres from one variable only:

- `POSTGRES_URL`

Do not keep dev/prod DB URL switching logic in application code.

Also add explicit settings for:

- `SUTRA_HERMES_HOMES_ROOT`
  - root directory on mounted NFS where agent homes live
  - on Cloud Run + Filestore this should point at the mount root, for example `/mnt/hermes`
  - hosted agent homes then live under `/mnt/hermes/.hermes/profiles/agent-<uuid>`
- `SUTRA_FIREBASE_SERVICE_ACCOUNT_JSON`
  - for real auth verification
- `SUTRA_DEV_AUTH_BYPASS`
  - local/dev-only shortcut for integration tests

---

## Filesystem Contract

Each agent has two separate identifiers:

### `hermes_home_path`

This is the real Hermes profile root on GCP NFS. It should look like a Hermes profile created from `profiles.py`.

Required directories:

- `memories/`
- `sessions/`
- `skills/`
- `skins/`
- `logs/`
- `plans/`
- `workspace/` (placeholder only; not the real Modal workspace source of truth)
- `cron/`

Seed files:

- `SOUL.md`
- optionally `memories/USER.md`
- optionally `memories/MEMORY.md`

### `workspace_key`

This is the durable identifier used later by the Modal execution layer.

For MVP, this can be deterministic and simple, for example:

- `agent:{agent_id}`

We should store the key, not a local path, because the workspace belongs to the execution plane.

---

## Service Boundaries

Keep routes thin and move all behavior into a few services.

### `AuthPrincipal`

Normalized authenticated identity used by the app:

- `user_id`
- `email`
- `name`

For login/bootstrap we also need an external identity shape sourced from the auth provider:

- `firebase_uid`
- `email`
- `name`

### `EnsureUserService`

Responsibilities:

- upsert the `User` from auth claims
- never create duplicates

### `EnsureUserAgentService`

Responsibilities:

- after user upsert, check whether the user has any agents
- if none exist, create exactly one initial agent

This replaces the need for an `is_default` field.

### `CreateAgentService`

Responsibilities:

- create `Agent` row
- assign deterministic `hermes_home_path`
- assign deterministic `workspace_key`
- call `ProvisionHermesHomeService`

### `ProvisionHermesHomeService`

Responsibilities:

- create the Hermes-compatible profile directory structure
- seed starter files
- optionally call Hermes skill seeding through a subprocess using the same pattern as `seed_profile_skills(...)`

Important rule:

- if we reuse Hermes code for skill seeding or future bootstrap logic, do it in a subprocess or dedicated bootstrap runner with `HERMES_HOME` set first
- do not import home-sensitive Hermes runtime modules directly inside request handlers

---

## API Surface

Only add what we need now.

### `GET /me`

Behavior:

- verify auth
- upsert user
- ensure one initial agent exists if user has none
- return user + agents

This endpoint should be idempotent.

### `GET /agents`

Behavior:

- list agents for the authenticated user

### `POST /agents`

Input:

- `name`

Behavior:

- create new agent for authenticated user
- provision `hermes_home`
- return created agent

---

## Concrete Implementation Order

### Step 1: Settings cleanup

- update backend settings loading to use `POSTGRES_URL`
- remove assumptions about local DB bootstrap
- add typed settings for homes root and auth mode

Reasoning:
- keep environment choice in one place so application code never branches on infra details

### Step 2: Tighten the models

- update `Agent` to include only:
  - `user_id`
  - `name`
  - `hermes_home_path`
  - `workspace_key`
- leave `User` mostly as-is
- avoid adding runtime lifecycle tables

Reasoning:
- this flow only needs ownership and provisioning outputs

### Step 3: Migration update

- generate a new Alembic migration for the model changes
- keep migration history clean and linear

Reasoning:
- Alembic is already set up correctly; use it rather than manual schema drift

### Step 4: Auth dependency

- add a backend auth module that:
  - validates Firebase tokens only at the login / token-exchange boundary
  - enforces `email_verified`
  - issues Sutra JWTs for normal app API access
  - supports a dev bypass path when configured
  - produces an app-facing `AuthPrincipal`

Reasoning:
- route handlers should not know about Firebase internals
- normal API traffic should not pay Firebase verification cost on every request

### Step 5: User upsert service

- implement `EnsureUserService`
- unique lookup by `firebase_uid`
- update `email` and `name` on repeat login if they changed

Reasoning:
- auth identity is the natural source of truth for user creation

### Step 6: Hermes-home path strategy

- decide a deterministic home path format under `SUTRA_HERMES_HOMES_ROOT`
- recommended format:
  - `<root>/.hermes/profiles/agent-<agent_id>/`

Reasoning:
- stable and easy to inspect during support/debugging
- mirrors Hermes' own profile layout, so `HERMES_HOME` points at something that already looks like a native Hermes profile root

### Step 7: Provisioning service

- implement `ProvisionHermesHomeService`
- create Hermes profile directories matching `hermes_cli/profiles.py`
- seed starter identity files
- optionally seed bundled skills using Hermes' subprocess pattern

Reasoning:
- this is the cleanest place to interface with Hermes without importing too much runtime code into the app

### Step 8: Agent creation service

- implement `CreateAgentService`
- generate `workspace_key`
- create DB row
- provision home
- return created agent

Reasoning:
- one service should own the transaction and side effects for agent creation

### Step 9: First-agent bootstrap service

- implement `EnsureUserAgentService`
- if user has no agents, create one named predictably, for example `"Agent"`

Reasoning:
- the "default first agent" behavior belongs here, not in database schema

### Step 10: Routes

- add:
  - `POST /auth/exchange`
  - `GET /me`
  - `GET /agents`
  - `POST /agents`

Reasoning:
- minimal user-visible surface for Phase 1 backend

### Step 11: Local integration tests

Add tests for:

- first auth creates user
- first auth creates exactly one agent
- repeat `GET /me` does not create another agent
- `POST /agents` creates another agent
- provisioning creates expected home directories/files

Reasoning:
- these tests protect the actual product promise: login and immediately have an agent

### Step 12: GCP dev smoke test

- deploy backend to dev Cloud Run
- point to dev Neon database
- mount the dev NFS root for Hermes homes
- verify:
  - first login creates user + first agent
  - second agent creation works
  - created NFS home has expected structure

Reasoning:
- this work is infra-sensitive enough that local-only testing is not sufficient

---

## Clean Interface With Hermes

Use Hermes in three layers only:

1. **Filesystem contract**
   - mirror Hermes profile layout

2. **Bootstrap helpers**
   - reuse subprocess-based skill seeding pattern where useful

3. **Future runtime adapter**
   - a dedicated Hermes runner/bootstrap module that sets `HERMES_HOME` before importing Hermes runtime

Avoid:

- importing `run_agent.py` directly inside FastAPI route modules
- mutating `HERMES_HOME` inside a long-lived shared process and then reusing already-imported Hermes modules
- building a Sutra-specific fake home layout that diverges from Hermes profile expectations

---

## Explicit Non-Goals For This Slice

Do not implement yet:

- chat execution
- SSE streaming
- Modal terminal execution
- background provisioning workers
- agent runtime lifecycle state machines
- replacing Hermes SQLite with Postgres
- multiple simultaneous top-level sessions per agent

Those can be added later without disturbing this initial backend slice if we keep the model small now.
