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
