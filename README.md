# DocuMind — AI PDF Chatbot

> Upload PDFs and chat with them using AI. Get cited, grounded answers with page references.

**Live Demo:** [https://documind-frontend-static.onrender.com](https://documind-frontend-static.onrender.com)  
**Backend API:** [https://documind-backend-free.onrender.com/docs](https://documind-backend-free.onrender.com/docs)

---

## What it does

- Upload one or more PDF documents
- Ask natural language questions about their contents
- Get accurate answers with inline citations (filename + page number)
- Chat across multiple documents at once
- Conversations are persisted — pick up where you left off

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, custom CSS (glassmorphism) |
| Backend | FastAPI (Python 3.11) |
| LLM | Groq — `llama-3.3-70b-versatile` |
| Embeddings | Google Gemini — `gemini-embedding-2` |
| Vector Search | Supabase pgvector (cosine similarity) |
| Keyword Search | BM25 (rank-bm25) — hybrid retrieval with RRF fusion |
| Database | Supabase Postgres |
| File Storage | Supabase Storage (private bucket) |
| Auth | JWT + Google OAuth 2.0 |
| Deployment | Render (frontend static site + backend Docker) |

---

## Architecture

```
User → React Frontend (Render Static)
          ↓ HTTPS
     FastAPI Backend (Render Docker)
          ↓
     ┌────────────────────────────────┐
     │  PDF Upload → Supabase Storage │
     │  Parse (PyMuPDF + Tesseract)   │
     │  Chunk → Embed (Gemini)        │
     │  Store → Supabase pgvector     │
     └────────────────────────────────┘
          ↓  Query time
     Hybrid Retrieval (pgvector + BM25 + RRF)
          ↓
     Groq LLM (streaming SSE)
          ↓
     Cited answer → User
```

---

## Retrieval Pipeline

1. **Dense vector search** — Gemini embeddings + pgvector cosine similarity
2. **Sparse BM25 search** — keyword matching over all chunks
3. **RRF fusion** — Reciprocal Rank Fusion combines both ranked lists
4. **Reranking** — term overlap + section heading boost + exact phrase bonus
5. **Summary injection** — for summary questions, document summary is prepended to context

---

## Features

- **Hybrid RAG** — vector + BM25 + RRF for higher retrieval accuracy
- **Streaming responses** — SSE streaming via Groq, no wait for full answer
- **Source citations** — every answer cites filename and page number
- **Multi-document chat** — ask across several PDFs in one conversation
- **Processing queue** — durable background worker with heartbeat, retry, and recovery
- **Restart-safe** — files in Supabase Storage, vectors in pgvector, all persisted across redeploys
- **Google OAuth** — sign in with Google or email/password
- **Responsive dark UI** — glassmorphism design, skeleton loading, no flash states

---

## Running Locally

### Backend

```bash
cd backend
cp ../.env.example .env   # fill in your keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, proxies `/api` to `http://localhost:8000`.

---

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase Postgres Session Pooler URI |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (backend only) |
| `SUPABASE_STORAGE_BUCKET` | Storage bucket name (`pdf-documents`) |
| `GROQ_API_KEY` | Groq API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `JWT_SECRET_KEY` | Secret for signing JWTs |
| `FRONTEND_URL` | Frontend origin (for CORS + OAuth redirect) |

---

## Deployment

Both services deploy automatically on push to `master` via `render.yaml`.

- **Frontend** — Render Static Site, Vite build, SPA rewrite rules
- **Backend** — Render Docker (python:3.11-slim + Tesseract OCR)

> Note: Render free tier spins down after 15 min inactivity. First load after idle may take ~30–60 seconds while the backend wakes up. The UI shows a "waking up" message during this time.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, chat, documents)
│   │   ├── core/         # Config, database, security
│   │   ├── models/       # SQLAlchemy ORM models
│   │   └── services/     # PDF parser, chunker, embedder, retriever, LLM, storage
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # React UI components
│   │   ├── hooks/        # useAuth, useDocuments, useChat
│   │   └── services/     # API client (axios + fetch for SSE)
│   ├── Dockerfile
│   └── vite.config.js
└── render.yaml           # Render deployment config
```

---

Built by [Kanish Mehan](https://github.com/kanish818)
