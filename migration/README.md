# Migration evidence archive

The production migration is complete. This directory retains:

- `manifests/`: generated API, database, Redis, configuration and resource inventories.
- `samples/`: fixed HTTP, database, knowledge-base and realtime protocol samples.
- `model-proxy/`: redacting HTTP/WebSocket recording proxy used by protected acceptance.
- `scripts/realtime_artifact.py`: SSE/WebSocket artifact helpers.
- `scripts/pdf_visual_compare.py`: deterministic PDF rendering comparison helper.
- `scripts/production_model_acceptance.py`: protected production model smoke check.

Regenerate and verify committed inventories:

```bash
./migration/scripts/generate-manifests.sh
./migration/scripts/check-manifests.sh
```

Runtime reports remain ignored under `migration/reports/`. Final migration evidence is
also preserved in GitHub Actions artifacts, the `pre-python-switch` tag, and the
archived pre-switch image.
