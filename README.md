# AI Radar

AI-assisted research discovery and source-linked paper reading. Search an official arXiv category, explore an overview of up to five recent papers, then select papers or upload PDFs for single-paper or joint reading.

## Demo

Watch [the English demo with captions](https://chuanghu07.github.io/ai-radar/) or [download the MP4](https://raw.githubusercontent.com/ChuangHu07/ai-radar/main/demo/AI-Radar-demo-en.mp4). It shows the working local interface and previously generated real reports. The separate two-paper example is labeled explicitly. Generation waiting time is omitted; this is an edited application walkthrough, not a claim of live inference.

## Features

- Official arXiv categories and exact subcategory search, such as `cs.AI`.
- Plain-language overviews, concept illustrations, research context, results and limitations.
- An editable reading collection: one paper for close reading, two to ten for joint analysis.
- Extractable-text PDFs up to 50 MiB and 150 pages each; scanned PDFs are unsupported.
- Source excerpts with physical PDF page references and links to original papers.
- Chinese/English interface; Chinese, English and bilingual reports.
- Persistent category shortcuts and official archive-level monthly submission counts, with the month shown. These are submission counts, not popularity or citation rankings.
- Explicit generation, bounded retries, usage accounting and visible failure states.

## Local setup

Use Python 3.12 or newer and Node.js 22.12 or newer. Windows has been tested; macOS commands are supplied but hardware validation is optional and has not been completed.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
npm run build
cd ..
./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### macOS Terminal

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
test -f .env || cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Before starting, edit `.env` locally with your own provider key and contact email. Never commit it. The default provider is Qwen; Claude is an explicit alternative, with no automatic paid fallback. Provider names, availability and billing are account-dependent. New model requests incur charges, and PDFs are sent to the selected model provider. Open http://127.0.0.1:8000 and keep the server terminal running.

## Development and checks

Run `python -m pytest tests -q` inside the virtual environment, and `npm run build` inside `frontend/`. For separate frontend development, `npm run dev` proxies API calls to port 8000.

The current source passed 216 backend tests and the production frontend build on Windows on 2026-10-18. Tests use synthetic fixtures and mocked model calls, not scientific validation of generated research claims. The build reports a non-blocking bundle-size warning.

## Architecture

`frontend/src/` contains the React/TypeScript interface. `backend/app/` contains FastAPI routes, PDF parsing, arXiv acquisition, model providers, evidence validation, report generation and language conversion. Tests are in `tests/`. Sanitized planning documents are in `devpost/`.

The model selects evidence identifiers from retained source text; deterministic checks validate identifiers, numeric references, structures and language preservation. Automated review is fallible. Readers must inspect the source, particularly equations, image-only details and cross-paper inferences.

## Proof-of-concept limits

Normal paper/report sessions are temporary and are cleared when the local processing service restarts; category settings persist. Saved review artifacts used in the video are separate from normal sessions and are not bundled here. arXiv/provider access may fail. Failed materials must be replaced or removed before deep reading can start. This local proof of concept has no accounts, public deployment, OCR, or claim of human-certified scientific accuracy.

This publication snapshot includes application source, tests, dependency locks, sanitized plans and the demo. It excludes credentials, personal learner context, local reports, source PDFs, usage ledgers, caches and the private development Git history. No license grant beyond applicable repository-hosting terms is implied; dependencies retain their own licenses.
