# AI-native application delivery factory

A customer-neutral, standard-library Python prototype that converts a structured requirement into a traceable backlog, a runnable HTTP service, tests, and deployment preparation. The "agents" are deterministic, limited workflow stages; no external AI model or credentials are required. The template is a starting point, **not** a production certification or autonomous deployment system.

## Quick start

Python 3.10+ is required. From the repository root:

```sh
python3 -m factory plan examples/requirement.json --output .factory-output
python3 -m factory status --output .factory-output
# Inspect .factory-output/backlog.json and .factory-output/requirement.json first.
python3 -m factory approve plan --reviewer "Demo reviewer" --output .factory-output
python3 -m factory implement --output .factory-output
python3 -m factory verify --output .factory-output
# Inspect the generated application, test result, and review.json.
python3 -m factory approve implementation --reviewer "Demo reviewer" --output .factory-output
python3 -m factory prepare --output .factory-output
# Inspect deploy/deployment.yaml and deploy/workflow.yml. This does not deploy.
python3 -m factory approve deployment --reviewer "Demo reviewer" --output .factory-output
python3 -m factory status --output .factory-output
```

Run the generated sample locally with `cd .factory-output && python3 app.py`, then visit `http://127.0.0.1:8000/health` or `/`. Run repository tests with `python3 -m unittest discover -s tests -v`. Use a new, empty output directory for each run; the tool never overwrites an existing run. See [architecture and governance](docs/architecture.md) for gates, limitations, and the artifact map.

Only provide synthetic, public, or newly generated customer-neutral requirements. Do not enter private meeting material, customer identifiers, proprietary source, secrets, or organization-specific configuration.
