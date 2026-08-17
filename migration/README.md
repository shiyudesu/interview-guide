# Migration workspace

This directory contains executable compatibility evidence for the Java-to-Python
migration. Generated Stage 0 inventories are committed under `manifests/`; runtime
samples and comparison reports are added in later stages.

```bash
./migration/scripts/generate-manifests.sh
./migration/scripts/check-manifests.sh
./migration/scripts/sync-flyway-schema.py
./migration/scripts/sync-java-resources.py
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
./migration/scripts/run-schema-comparison.sh
./migration/scripts/run-interview-schedule-comparison.sh
./migration/scripts/run-interview-skill-comparison.sh
./migration/scripts/run-llm-provider-comparison.sh
./migration/scripts/run-resume-foundation-comparison.sh
./migration/scripts/run-resume-upload-comparison.sh
./migration/scripts/run-voice-rest-comparison.sh
./migration/scripts/run-knowledge-base-comparison.sh
./migration/scripts/run-failure-cases.sh
./migration/scripts/stop-model-proxy.sh
./migration/scripts/stop-comparison-env.sh
```

The default candidate is a second isolated Java instance, so Java-to-Java comparison
must produce zero differences throughout migration. Set `COMPARISON_CANDIDATE=python`
for module-scoped Python comparisons. `auto` switches only after the explicit
`backend/.comparison-ready` final-cutover marker exists. Runtime logs and JSON/HTML
reports are written under the ignored `migration/reports/` directory. Passing
`--purge` to the stop script explicitly deletes only comparison volumes.

SSE, WebSocket, file, and visible PDF evidence can be captured with the locked
backend dependencies:

```bash
cd backend
uv run python ../migration/scripts/realtime_artifact.py --help
```

The knowledge-base comparison uses the committed TXT/Markdown fixtures under
`samples/knowledge-base/`. It compares synchronous HTTP, PostgreSQL, Redis Stream,
and S3 state. It does not invoke or claim validation of a real Embedding model.

Java production defaults remain unchanged. Comparison processes opt into deterministic
values with `interview.guide.migration.*` system properties:

- `fixed-time`: ISO local date-time used by persistence and scheduler code.
- `uuid.<purpose>`: comma-separated UUID sequence.
- `bytes.<purpose>`: comma-separated hexadecimal byte sequence, including AES-GCM nonces.
- `int.<purpose>`: comma-separated deterministic random selections.
- `millis.<purpose>`: comma-separated real-time protocol timestamps.
- `string.tts-websocket-url`: test-only TTS proxy endpoint.
- `consumer-suffix`: fixed Redis Stream consumer suffix.
- `disable-stream-consumers`: keeps API-only comparison queues deterministic.

Configured sequences fail when exhausted instead of silently reusing an ID or nonce.
