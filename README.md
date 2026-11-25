# Legacy Application Understanding Accelerator

A customer-neutral proof of value for assessing **synthetic or public Python source**.
It inventories behavior candidates, imports and local calls, technical risks, treatment
candidates, a prioritized backlog, and a phased modernization plan. It never imports
or executes the code under assessment. All findings are static hypotheses to validate,
not a substitute for runtime observation, tests, or business-owner review.

## Run

Requires Python 3.10+; no installation or third-party dependencies are needed.
From the repository root:

```sh
python -m examples.legacy_app
python -m legacy_accelerator examples/legacy_app --output /tmp/legacy-assessment
cat /tmp/legacy-assessment/report.md
python -m unittest discover -s tests -v
```

`assessment.json` contains structured findings; `report.md` contains the dependency
map, evidence-backed treatment paths (retain, rehost, replatform, refactor or rewrite
when the corresponding signal exists), modernization backlog, phased plan, and
concise proof-of-value summary. Paths and line numbers point to the source used.
The included order, pricing, and CSV example is newly generated, synthetic code.
Pass a `.py` file or directory as the source; analyze only material you are authorized
to use. Keep output outside the source tree and do not share assessments of private
code. The application-specific assessment is not checked in.

See [architecture and rule limitations](docs/architecture.md).
