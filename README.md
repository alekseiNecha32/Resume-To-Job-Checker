# Resume ATS Checker

Optimize a resume against a job description. The app extracts hard technical skills, computes a fit estimate using MiniLM, and generates concise “Personal Suggestions” via OpenAI (gpt-4.1-mini). Smart Analysis consumes 1 credit.

## Features
- Upload resume (PDF/DOCX/TXT) and paste job description.
- MiniLM-based matching:
  - Fit estimate (heuristic)
  - Present vs missing hard skills
  - Critical gaps
  - Section-specific suggestions
- OpenAI “Personal Suggestions” (hard skills only; ignores soft skills).
- Auth, credits, and Stripe checkout.
- CORS-safe API with OPTIONS preflight.

## Tech Stack
- Frontend: React + Vite
- Backend: Flask + Supabase
- ML: MiniLM, KeyBERT
- LLM: OpenAI gpt-4.1-mini (suggestions only)
- Deploy: Render

## Monorepo Layout
- `frontend/` — React app (Vite)
- `backend/` — Flask API
  - `app/blueprints/smart.py` — Smart Analysis endpoint
  - `app/__init__.py` — App factory, CORS, OpenAI client init

## Environment Variables

Frontend (`frontend/.env` and `.env.production`)
```
VITE_API_URL_Dev=http://127.0.0.1:5000/api
VITE_API_URL_Prod=https://<your-backend-host>/api
```

Backend (`backend/.env` or Render env settings)
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=sk-...
SECRET_KEY=change-me
```

## OpenAI Usage
- Only “Personal Suggestions” use OpenAI.
- Model: `gpt-4.1-mini`
- If quota/rate limit fails, backend returns `personal_suggestions_error` and continues with MiniLM results.

## CORS
- Enabled for `/api/*` with allowed origins:
  - `http://localhost:5173`, `http://127.0.0.1:5173`, and your production frontend.
- `smart.py` handles `OPTIONS` preflight on `/api/smart/analyze` (returns 204).

## Running Locally (Windows)

Backend
```
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Either set env vars in PowerShell or keep them in backend/.env
python run.py  # or: flask run --host 127.0.0.1 --port 5000
```

Frontend
```
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 and test. The frontend will call `http://127.0.0.1:5000/api`.

## Deploy (Render)
- Backend service: add env vars (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY) and deploy.
- Frontend: set `VITE_API_URL_Prod` to your backend URL and deploy.

## Smart Analysis Flow
1. Frontend posts to `/api/smart/analyze` with resume_text, job_text, job_title and Authorization.
2. Backend runs MiniLM scoring/skills.
3. Backend calls OpenAI for “Personal Suggestions” with a hard-skills-only prompt.
4. Credits are deducted and results saved.
5. Response includes MiniLM fields plus `personal_suggestions`.

## Troubleshooting
- CORS error: ensure backend allows your frontend origin and `OPTIONS` returns 204 on `/api/smart/analyze`.
- OpenAI 429 “insufficient_quota”: suggestions will be omitted; add credits or handle `personal_suggestions_error` in UI.
- Flicker on profile: MeContext caches profile in localStorage and Navbar uses cached while loading.

## License
Proprietary. All rights reserved.