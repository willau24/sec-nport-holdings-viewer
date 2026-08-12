# N-PORT Viewer — Frontend

React SPA for entering a CIK and viewing a fund's N-PORT holdings. Handles the
multi-fund trust case with a picker, and renders large filings through a
virtualized table with client-side sorting and filtering.

## Build

```bash
npm install
npm run build
```

Output goes to `dist/`, which the backend serves in production.

## Run

```bash
npm run dev
```

Open http://localhost:5173. Requires the backend running on port 8000 — Vite
goes through `/api` to it, so the app stays same-origin.

## Test

```bash
npm test
```

21 tests covering the formatting layer. Typechecks `tests/` before running.