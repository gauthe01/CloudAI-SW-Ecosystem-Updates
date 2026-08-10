# Feature 22 - Enterprise AI Runtime Foundation

## Purpose

Feature 22 introduces the production-shaped AI runtime foundation for Cloud AI
Software Ecosystem Updates. It prepares the backend and worker to call an
enterprise OpenAI-compatible endpoint without placing model calls directly
inside webhook handlers, UI code, or connector-specific services.

This feature does not yet extract updates with AI. It creates the safe shared
runtime that later agent features will use.

## Backend Scope

- Add runtime settings for an enterprise OpenAI-compatible endpoint.
- Add the OpenAI Python SDK and explicit HTTP client dependency to the backend
  image.
- Add a single AI client factory under `app.agents.runtime`.
- Validate required settings before any model call is attempted.
- Keep AI disabled by default in local development.
- Support enterprise CA bundle configuration for corporate network trust.
- Add unit tests that verify config behavior without calling an external model.

## Environment Variables

| Variable | Required when enabled | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | yes | Use `enterprise_openai_compatible` to enable AI runtime. |
| `AI_BASE_URL` | yes | Enterprise OpenAI-compatible API base URL. |
| `AI_API_KEY` | yes | API key or token from the approved enterprise provider. |
| `AI_MODEL_UPDATE_EXTRACTION` | yes | Model/deployment used by source-event extraction agents. |
| `AI_MODEL_REPORTING` | optional | Model/deployment used by presenter/reporting agents. |
| `AI_TIMEOUT_SECONDS` | no | Request timeout for model calls. |
| `AI_MAX_RETRIES` | no | SDK retry count for transient model call failures. |
| `AI_CA_BUNDLE` | optional | Path to a corporate CA bundle inside the API/worker container. |
| `RULEBOOK_DIR` | yes | Developer-owned rulebook directory for later agent behavior. |

## AWS Deployment Shape

The AI runtime belongs inside the existing backend image for now:

- API container: validates settings, exposes future agent endpoints, and records
  request/audit metadata.
- Worker container: performs asynchronous source-event extraction and reporting
  jobs using the same runtime module.
- Secrets: `AI_API_KEY` and any provider credentials must come from AWS Secrets
  Manager or SSM Parameter Store, not from committed files.
- Network: EC2/ECS tasks need outbound access to the enterprise endpoint through
  the approved corporate route/proxy.
- Certificates: if the enterprise endpoint requires a private CA, mount the CA
  bundle into the API and worker containers and set `AI_CA_BUNDLE`.

Splitting AI into a separate service is intentionally deferred. It becomes
useful only if agent workloads need independent scaling, GPU-adjacent services,
or stricter isolation from the main API.

## Not In Scope

- No prompt/rulebook execution yet.
- No AI source-event extraction yet.
- No presenter intelligence model call yet.
- No UI changes.
- No database migration; existing `agent_runs` already provides the first audit
  table for model-backed runs.

## Acceptance Criteria

- App starts with `AI_PROVIDER=disabled`.
- Missing AI endpoint/key/model fails fast with clear configuration errors once
  AI is enabled.
- Client construction trims trailing slashes from `AI_BASE_URL`.
- Tests do not call the external enterprise endpoint.
- API and worker Docker images install the same AI runtime dependency.
