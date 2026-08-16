# Migration workspace

This directory contains executable compatibility evidence for the Java-to-Python
migration. Generated Stage 0 inventories are committed under `manifests/`; runtime
samples and comparison reports are added in later stages.

```bash
./migration/scripts/generate-manifests.sh
./migration/scripts/check-manifests.sh
```

The generator uses only the Python standard library. It scans Java controller and
WebSocket mappings, frontend URL usage, Flyway SQL, Redis constants and operations,
configuration sources, prompts, skills, scripts, and existing tests. Unmatched
frontend/backend paths are evidence to preserve and investigate, not permission to
change behavior.

The Stage 1 comparison environment uses independent PostgreSQL databases, Redis
instances, ports, and S3 buckets:

```bash
./migration/scripts/start-comparison-env.sh
./migration/scripts/start-model-proxy.sh
./migration/scripts/record-java-baseline.sh
./migration/scripts/capture-runtime-state.sh
./migration/scripts/run-comparison.sh
./migration/scripts/run-failure-cases.sh
./migration/scripts/stop-model-proxy.sh
./migration/scripts/stop-comparison-env.sh
```

Until `backend/pyproject.toml` exists, the candidate port runs a second isolated Java
instance so Java-to-Java comparison must produce zero differences. Set
`COMPARISON_CANDIDATE=python` after the Python application is available. Runtime
logs and JSON/HTML reports are written under the ignored `migration/reports/`
directory. Passing `--purge` to the stop script explicitly deletes only comparison
volumes.
