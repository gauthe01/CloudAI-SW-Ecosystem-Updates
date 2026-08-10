# Feature 24C.1 - Controlled AI Dry-Run Probe

## Purpose

Feature 24C.1 adds a backend operational probe for the enterprise
OpenAI-compatible endpoint.

The probe answers one narrow question:

Can the configured AI endpoint accept a Cloud AI Software Ecosystem Updates
source-event extraction request and return JSON that passes the Feature 24B
output contract?

## What It Does

- Builds one synthetic source event in memory.
- Forces extraction mode to `dry_run` for that probe invocation only.
- Calls the same model adapter used by Feature 24C.
- Validates the response through the Feature 24B contract.
- Prints a redacted JSON report.

## What It Does Not Do

- It does not insert a `source_event`.
- It does not insert a `source_payload`.
- It does not insert a `partner_update`.
- It does not depend on any real partner, contributor, or connected source row.
- It does not read or write anything in `Gold/`.

## Command

Run from the project root:

```sh
docker compose run --rm api python -m app.tools.source_event_dry_run_probe --pretty
```

Optional source-specific probe:

```sh
docker compose run --rm api python -m app.tools.source_event_dry_run_probe \
  --source-type jira_issue \
  --source-url "https://jira.example.com/browse/AWS-123" \
  --technical-metadata-json '{"probe":true,"issue_key":"AWS-123","status":"In Progress"}' \
  --pretty
```

## Required Configuration

The container environment must have:

- `AI_PROVIDER=enterprise_openai_compatible`
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL_UPDATE_EXTRACTION`

Optional:

- `AI_TIMEOUT_SECONDS`
- `AI_MAX_RETRIES`
- `AI_CA_BUNDLE`
- `AI_SOURCE_EVENT_MAX_OUTPUT_TOKENS`

Current local validation uses:

```env
AI_BASE_URL=https://openai-api-proxy.geo.arm.com/api/providers/openai-us/v1
AI_MODEL_UPDATE_EXTRACTION=gpt-4o
AI_CA_BUNDLE=/app/certs/ARM-Enterprise-PKI-Root-CA.pem
```

`gpt-5o` is not a valid model name for the current proxy endpoint/key.

## Corporate CA Bundle

If the probe fails with `CERTIFICATE_VERIFY_FAILED`, the Docker container does
not trust the enterprise certificate chain.

Place the approved corporate CA bundle in:

```txt
certs/
```

Then set:

```env
AI_CA_BUNDLE=/app/certs/<ca-bundle-file>.pem
```

The `certs/` folder is mounted read-only into both API and worker containers.
Certificate files in that folder are ignored by git.

The backend also includes `truststore` as a fallback so Python can use the
runtime's system trust store where that is sufficient. The explicit
`AI_CA_BUNDLE` path still takes priority for Docker and production clarity.

The probe does not require changing `AI_SOURCE_EVENT_EXTRACTION_MODE` in `.env`
because it forces dry-run for its own process only.

## Successful Output

The probe returns JSON with:

- `status=succeeded`
- Redacted runtime readiness
- `result.extraction_mode=model_dry_run`
- `result.model_output_validated=true`
- `database_writes.partner_updates=0`

## Failure Output

If AI is disabled or misconfigured, the command exits with code `1` and prints a
redacted JSON error. Secret values are not printed.

Connection and certificate failures are also returned as redacted JSON so the
probe can be used safely during environment setup.

## Deployment Notes

This is not a separate service. It ships in the backend image and can be run as a
one-off command in Docker Compose, EC2, ECS, or any future worker runtime.

Recommended AWS usage:

- Run it as a one-off backend task after secrets are configured.
- Keep the long-running worker at `AI_SOURCE_EVENT_EXTRACTION_MODE=infrastructure_only`
  until dry-run behavior is reviewed.
- Use the probe before enabling staging workers in `dry_run` mode.

## Next Step

After this probe succeeds against the real endpoint, the next safe step is to
review dry-run behavior with the real rulebook content from Feature 23B/23C
before Feature 24D creates contributor-reviewable draft updates.
