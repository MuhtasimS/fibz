# CI.md — Continuous Integration for Fibz

This guide explains how the GitHub Actions CI for **Fibz** is set up, what it runs, and how to configure secrets and troubleshoot failures. It’s written for project maintainers and contributors.

---

## What the workflow does

The workflow (see `.github/workflows/ci.yml`) runs on **push** and **pull_request** to the `main`/`master` branches. It:
- Runs a **Python matrix** on `3.10`, `3.11`, and `3.12`.
- Caches **pip** dependencies.
- Installs the project with dev extras: `pip install -e ".[dev]"`.
- Lints with **Ruff** (annotated in PR), checks formatting with **Black**, runs **mypy** type checks.
- Executes **pytest** with coverage and uploads coverage artifacts (`coverage.xml`, plus `.pytest_cache`).

The workflow uses **concurrency** to cancel in-progress runs for the same branch when a new push arrives.

---

## One‑time setup

### 1) Add repository secrets (recommended baseline)
Open **Settings → Secrets and variables → Actions → New repository secret** and add any that apply:

| Secret name | Required? | What it’s for |
|---|---:|---|
| `DISCORD_BOT_TOKEN` | Optional | Needed only if you run Discord **integration** tests. Unit tests should not require it. |
| `GCP_PROJECT_ID` | Optional | Used by integration tests hitting Vertex AI (prefer stubs for CI). |
| `GCP_VERTEX_LOCATION` | Optional | E.g., `us-central1`. |
| `GOOGLE_CSE_ID` | Optional | Only if tests exercise live web search. Prefer stubbed fixtures for CI. |
| `GOOGLE_CSE_API_KEY` | Optional | Only if tests exercise live web search. |
| `GCS_BUCKET` | Optional | For integration tests that actually write to GCS (use a test bucket). |
| `GCP_SA_JSON` | Optional | A **JSON blob** of a service account key, if you really need cloud calls in CI. The workflow writes it to `sa.json` and sets `GOOGLE_APPLICATION_CREDENTIALS` accordingly. |

> **Best practice:** CI should prefer **stubbed** or **fixture** responses. Keep cloud access disabled unless you are intentionally running integration tests.

### 2) Optional: Service account (GCP)
If you must hit GCP in CI, create a dedicated **service account** with **least privilege** for your test environment and upload its JSON to `GCP_SA_JSON` secret. Most unit tests should work **without** this—prefer mocks/stubs.

---

## `.env.ci` (optional)

The workflow can load a local `.env.ci` file (checked into the repo with **placeholders**, not real secrets). Any **non-empty** lines that aren’t comments are exported into the CI environment.

Template snippet (already provided as `env_ci.txt` you can copy to `.env.ci`):
```
DISCORD_BOT_TOKEN=__set_in_actions_secrets__
GCP_PROJECT_ID=your-project-id
GCP_VERTEX_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=${GITHUB_WORKSPACE}/sa.json
GOOGLE_CSE_ID=__set_in_actions_secrets__
GOOGLE_CSE_API_KEY=__set_in_actions_secrets__
GCS_BUCKET=fibz-ci-bucket
CHROMA_PATH=.chroma
ALLOW_DOMAINS=
DENY_DOMAINS=
```

> In CI, **real secrets** should live in GitHub Actions Secrets, not in `.env.ci`.

---

## Local parity — run the same checks locally

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff --fix .
black .
mypy fibz_bot
pytest -q --maxfail=1 --disable-warnings --cov=fibz_bot --cov-report=term
```

If you need the same environment variables locally, create `.env` (based on `.env.example`).

---

## Reading CI results

- **Ruff/Black/Mypy**: The job log shows exact errors. Ruff comments appear inline on PR diffs.
- **Pytest**: The summary shows failed tests. Coverage reports upload as an artifact (`coverage.xml`), which you can download from the job page.
- **Artifacts**: Look under the “Artifacts” section of the finished job for coverage files and caches.

---

## Common failures & quick fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Ruff errors | Style violations | Run `ruff --fix .` locally and commit. |
| Black check fails | Formatting drift | Run `black .` and commit. |
| mypy errors | Missing types/stubs or mismatched interfaces | Add/adjust type hints or install stubs (e.g., `types-requests`). |
| ImportError in tests | Dev deps missing | Ensure required test deps are listed in `pyproject.toml` under `.[dev]`. |
| Timeouts on web/GCP calls | Live calls in tests | Replace with stubs/fixtures; CI should not rely on external services. |
| Permission errors on GCP | Missing/incorrect `GCP_SA_JSON` or IAM role | Prefer stubs; if needed, verify service account and least-privilege roles. |

---

## Customizing the workflow

- **Python versions**: Edit the `matrix.python-version` list.  
- **Add platforms**: Duplicate the job for `windows-latest` or `macos-latest` if needed.  
- **Coverage tooling**: The workflow emits `coverage.xml`. You can add a Codecov step if you use that service.  
- **Selective test runs**: Use `pytest -k`, or split unit vs integration tests into separate jobs.  
- **Branch protections**: In **Settings → Branches**, require the CI job to pass before merging.

---

## Security notes

- Never commit real secrets. Use GitHub **Secrets** for sensitive values.
- Use dedicated **test resources** (e.g., a test GCS bucket) if you must run integration tests in CI.
- Principle of least privilege for any service account used in CI.

---

## FAQ

**Q: Do I need all the secrets for the CI to pass?**  
A: No. Unit tests should pass without secrets. Only integration tests require cloud config. Prefer stubs for CI.

**Q: Where do I see coverage?**  
A: Download `coverage.xml` from the job’s artifacts, or integrate Codecov/Sonar if you prefer dashboards.

**Q: Can I run just one Python version?**  
A: Yes—change the matrix to a single version (e.g., `["3.11"]`) if you want to speed up CI for a branch.

---

If you change the project structure, remember to update the workflow and this document to match.
