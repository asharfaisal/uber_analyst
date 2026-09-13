# Uber AI Analyst — Delhi/NCR

A conversational AI data analyst for a 150,000-row Uber ride dataset
(Delhi/NCR, full year 2025). Ask natural-language questions, get grounded
answers with charts.

## Architecture

```
├── api/analyze.py        # Vercel Python serverless function (the entire backend)
├── backend/               # Core logic, imported by api/analyze.py
│   ├── constants.py        # Column names, categorical values, dataset facts
│   ├── data_engine.py       # pandas loading, filtering, aggregation
│   ├── intent_schema.py     # Intent/Filters dataclasses + validation
│   ├── intent_classifier.py # Claude call: question -> structured Intent
│   ├── query_planner.py     # Deterministic: Intent -> data_engine calls
│   └── response_formatter.py# QueryResult -> chart JSON + Claude narrative
├── data/uber.xlsx         # The dataset (bundled with the deployment)
├── tests/                 # 66 passing tests covering the non-LLM logic
├── web/                   # React (Vite) frontend
└── vercel.json            # Wires the static frontend + Python function together
```

Only `intent_classifier.py` and `response_formatter.generate_narrative()` call
Claude. Everything else (filtering, aggregation, chart-data shaping) is
deterministic Python, which is why it's fully unit-tested without needing an
API key.

## Local development

**Backend tests** (no API key needed):
```bash
pip install -r requirements.txt
pip install pytest
python -m pytest tests/ -v
```

**Frontend:**
```bash
cd web
npm install
npm run dev
```
This proxies `/api/*` to `http://localhost:3000` (see `web/vite.config.js`) —
run `vercel dev` from the project root in a separate terminal to serve the
Python function locally.

## Deploying to Vercel

1. Push this repository to GitHub (or wherever Vercel pulls from).
2. In the Vercel dashboard, set the environment variable:
   - `ANTHROPIC_API_KEY` — your Claude API key (used server-side only, in
     `api/analyze.py`; it is never sent to the browser)
3. Deploy. `vercel.json` already tells Vercel to:
   - Build `web/` as a static site (Vite output → `web/dist`)
   - Deploy `api/analyze.py` as a Python serverless function, bundling
     `backend/**` and `data/uber.xlsx` alongside it (`includeFiles`)
4. Vercel routes `/api/analyze` to the Python function and everything else
   to the built frontend.

No database, no external services beyond the Claude API. The dataset is
loaded into memory once per warm serverless instance and reused across
requests to that instance.

## Extending

- **New question types**: add a value to `VALID_INTENT_TYPES` in
  `intent_schema.py`, a handler in `query_planner.py`'s dispatch dict, and a
  formatting branch in `response_formatter.py`. Add a test in
  `tests/test_query_planner.py` using a hand-built `Intent` before wiring up
  the classifier prompt — this validates the execution logic without an API
  call.
- **New chart type**: add a case in `web/src/App.jsx`'s render branch and a
  corresponding component (see `BarChart.jsx` / `LineChart.jsx` for the
  pattern — plain SVG, no charting library dependency).
