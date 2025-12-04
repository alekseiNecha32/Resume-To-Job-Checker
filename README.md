# Resume-To-Job-Checker

A small web app that compares a resume to a job description and gives simple, ATS-style feedback.  
It highlights missing technical skills, shows a match score, and gives suggestions to improve the resume before applying.

---

## 🌟 What this app does

- **Paste your resume and job description**
- **Get a match score** between the resume and the job
- **See missing technical skills / keywords**
- **Smart suggestions** on what to add or rewrite in your resume
- Designed for **junior developers and students** who want quick feedback before they apply

---

## 🧠 How it works (high level)

On the backend:

- Uses **sentence-transformers MiniLM** to create embeddings for the resume and job description  
- Uses **KeyBERT** and simple NLP rules to extract important keywords  
- Compares both texts and builds:
  - A similarity score
  - Lists of **matched** and **missing** skills/keywords
- Returns structured JSON that the frontend displays in a friendly way

Optionally, the app can be extended to call an **LLM API** (for example OpenAI) for more personal suggestions, while still using MiniLM/KeyBERT for the main technical keyword analysis.

---

## 🧰 Tech stack

**Frontend**

- React (JavaScript)
- Vite / Create React App (depending on current setup)
- Tailwind CSS / plain CSS (check `/frontend` for the exact stack)
- Calls the backend via REST API

**Backend**

- Python 3
- Flask
- `sentence-transformers` (MiniLM model)
- KeyBERT
- spaCy (basic NLP)
- Stripe (for paid “smart analysis”)
- (Optional) Supabase for auth and user storage

---

## 📁 Project structure

```text
Resume-To-Job-Checker/
├── backend/        # Flask API, ML/NLP logic, Stripe webhooks
├── frontend/       # React app (UI)
├── .gitignore
├── .gitattributes
└── README.md
