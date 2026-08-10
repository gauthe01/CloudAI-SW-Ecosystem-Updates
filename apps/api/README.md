# API And Worker

Target: FastAPI, Python, PostgreSQL, Alembic, SQS-compatible queues, and
S3-compatible storage.

The API and worker should share the same backend codebase but run as separate
processes.

Feature 01 will initialize the actual API runtime here.
