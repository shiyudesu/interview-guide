# Repository tools

This directory contains maintained quality and diagnostics tooling:

- `manifests/`: generated API, database, Redis, configuration, and resource inventories.
- `model-proxy/`: redacting HTTP/WebSocket proxy for provider diagnostics and fault tests.
- `scripts/`: manifest generation and protected production-model acceptance checks.
- `tests/`: tests for repository tooling.

Generate and verify the committed inventories:

```bash
./tools/scripts/generate-manifests.sh
./tools/scripts/check-manifests.sh
```

Generated runtime output is written under the ignored `.artifacts/` directory.
