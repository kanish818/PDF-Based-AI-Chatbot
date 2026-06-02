# DocuMind — PDF-Based AI Chatbot

> Upload PDF documents and ask questions about their contents using an AI-powered chatbot with hybrid search, streaming responses, and source attribution.

[![Live Demo](https://img.shields.io/badge/Live-Demo-6366f1?style=for-the-badge)](https://documind-frontend-free.onrender.com)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-gray?style=for-the-badge)](https://github.com/kanish818/PDF-Based-AI-Chatbot)

---

## 🌍 Live Application

| Service | URL |
|---------|-----|
| **Frontend (App)** | https://documind-frontend-free.onrender.com |
| **Backend API** | https://documind-backend-free.onrender.com |
| **API Docs (Swagger)** | https://documind-backend-free.onrender.com/docs |

> **Note:** Hosted on Render free tier — the service may take ~30 seconds to wake up on first visit.

---

## ✨ Features

- 📄 **Multi-PDF Upload** — Upload up to 50MB PDFs, multiple files supported
- 🔍 **Hybrid Search** — BM25 keyword search + vector search with Reciprocal Rank Fusion
- 🤖 **Streaming Responses** — Real-time token-by-token streaming via Groq LLaMA 3.3 70B
- 📍 **Source Attribution** — Every answer cites exact page numbers and excerpts
- 🔐 **Authentication** — Email/password + Google OAuth 2.0
- 💬 **Conversation Memory** — Full chat history preserved per session
- 📷 **OCR Support** — Scanned PDFs handled via Tesseract OCR
- 🧪 **Evaluation Harness** — Run benchmark datasets and generate Recall@k / MRR / citation reports
- 🐳 **Docker Ready** — One-command deployment with Docker Compose

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  FRONTEND (React + Vite)                     │
│   Upload UI │ Chat + Streaming │ Source Panel │ Auth UI      │
└──────────────────────┬──────────────────────────────────────┘
                       │  REST API + SSE (streaming)
┌──────────────────────▼──────────────────────────────────────┐
│                  BACKEND (Python FastAPI)                     │
│                                                              │
│  ┌─────────────┐   ┌──────────────────┐  ┌───────────────┐  │
│  │  PDF Parser  │   │   Embedder        │  │  Chat Engine  │  │
│  │  PyMuPDF     │   │  Gemini           │  │  Groq LLM     │  │
│  │  +Tesseract  │   │  gemini-          │  │  llama-3.3-   │  │
│  │  (OCR)       │   │  embedding-001    │  │  70b          │  │
│  └──────┬───────┘   └────────┬──────────┘  └───────┬───────┘  │
│         │                    │                      │          │
│  ┌──────▼────────────────────▼──────────────────────▼───────┐ │
│  │        ChromaDB (vector)  +  BM25 (keyword)              │ │
│  │              → RRF Hybrid Fusion → Top 5 chunks           │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │       SQLite: users + conversations + messages            │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │      Docker Compose      │
          │  backend + frontend      │
          └─────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite 5 |
| Backend | Python 3.11 + FastAPI |
| LLM | Groq `llama-3.3-70b-versatile` |
| Embeddings | Google Gemini `gemini-embedding-001` |
| Vector DB | ChromaDB (persistent) |
| Keyword Search | BM25 (`rank-bm25`) |
| PDF Parsing | PyMuPDF (fitz) |
| OCR | Tesseract + pytesseract |
| Auth | JWT + Google OAuth 2.0 |
| Database | SQLite + SQLAlchemy |
| Deployment | Docker Compose + Render.com |

---

## 🎯 Design Decisions

### Chunking Strategy
Documents are split using a **section-aware paragraph chunker**:
- **Chunk size**: ~1,600 characters
- **Overlap**: ~220 characters
- **Split strategy**: preserve headings, merge short paragraphs, and keep page-level metadata

Each chunk stores metadata such as `filename`, `page_num`, `chunk_index`, `section_heading`, `doc_id`, and `user_id`.

### Embedding Model
**Gemini `gemini-embedding-001`** is used because:
- Supports task-type hints: `RETRIEVAL_DOCUMENT` for indexing, `RETRIEVAL_QUERY` for queries
- Free tier: 1,500 requests/day on Google AI Studio — sufficient for this use case
- No local GPU required; runs via API

### Retrieval Approach (Hybrid Search)
We combine two complementary search methods:

1. **Vector Search** (ChromaDB cosine similarity) — top 10 results
   - Finds semantically similar content even with different wording
   
2. **Keyword Search** (BM25) — top 10 results  
   - Finds exact keyword matches, better for technical terms and proper nouns

3. **Reciprocal Rank Fusion (RRF)** fuses both lists, then a lightweight reranker boosts lexical overlap and heading relevance:
   ```
   score(d) = Σ 1 / (rank(d, list) + 60)
   ```
   - Final top chunks are passed to the LLM as grounded context

This hybrid approach significantly outperforms either method alone, especially for:
- Technical documents with specialized terminology (BM25 advantage)
- Conceptual questions where phrasing differs (vector advantage)

### Prompt Design
```
System: You are a helpful AI assistant that answers questions ONLY based on 
the provided PDF document excerpts below.
- Always cite your source as: [filename.pdf, Page X]
- Quote the exact relevant sentence as evidence  
- If the answer is not found in the documents, say:
  "I could not find information about this in the uploaded documents."
- Be concise and direct.

Context Documents:
[SOURCE 1] report.pdf | Page 4:
"...relevant text chunk..."

[SOURCE 2] report.pdf | Page 7:
"...another relevant chunk..."

Chat History:
[last 10 messages]

User: {question}
```

---

## 🚀 Setup Instructions

### Prerequisites
- Docker Desktop installed
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/kanish818/PDF-Based-AI-Chatbot.git
   cd PDF-Based-AI-Chatbot
   ```

2. **Configure environment**
   ```bash
   cp .env.example backend/.env
   # Edit backend/.env with your API keys
   ```
   
   Required keys:
   - `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
   - `GEMINI_API_KEY` — from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (starts with `AIzaSy...`)
   - `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` — from Google Cloud Console

3. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```
   
   - Frontend: http://localhost:80
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Manual Setup (without Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
# Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Visit http://localhost:5173
```

---

## 🌐 Deployment (Render.com)

This repo includes a Render Blueprint at [`render.yaml`](render.yaml).

Recommended flow:

1. Push the repo to GitHub.
2. In Render, choose **New + → Blueprint**.
3. Select this repository and keep the Blueprint path as `render.yaml`.
4. Provide only the required secret env vars:
   - `GROQ_API_KEY`
   - `GEMINI_API_KEY`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
5. Render creates:
   - `documind-backend` as a Docker web service with a persistent disk
   - `documind-frontend` as a Docker web service running Nginx
6. After the first deploy completes, add these Google OAuth settings:
   - Authorized JavaScript origin: `https://documind-frontend-free.onrender.com`
   - Authorized redirect URI: `https://documind-backend-free.onrender.com/api/auth/google/callback`

---

## 📁 Project Structure

```
pdf-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (auth, documents, chat)
│   │   ├── core/         # Config, database, security
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── services/     # PDF parser, embedder, retriever, LLM
│   │   └── main.py       # FastAPI app entry point
│   ├── eval/             # Dataset-driven retrieval / citation evaluation harness
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # React components (Auth, Chat, Upload, Sources)
│   │   ├── hooks/        # Custom React hooks (useAuth, useChat, useDocuments)
│   │   ├── services/     # API client (axios)
│   │   └── App.jsx       # Root component with routing
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── render.yaml
├── .env.example
└── README.md
```

---

## 🧪 Evaluation Workflow

The repo now includes a benchmark runner in [`backend/eval`](backend/eval).

What it measures:
- `Recall@1`, `Recall@3`, `Recall@5`
- `MRR`
- `citation_hit_rate` when answer generation is enabled
- `answer_phrase_coverage` when answer generation is enabled
- `no_answer_accuracy` for refusal cases

Quick start:

```bash
cd backend
python eval/run_eval.py --dataset eval/datasets/eval_dataset.example.json --user-email you@example.com
python eval/run_eval.py --dataset eval/my_eval_set.json --user-email you@example.com --with-llm
```

Reports are written to `backend/eval/reports/` as JSON and Markdown files.

---

## 📊 Evaluation Alignment

| Criterion | Implementation |
|-----------|---------------|
| **Correctness (30%)** | Groq LLaMA 3.3 70B with grounded context, strict page citations |
| **Retrieval Quality (25%)** | Hybrid BM25 + vector search with RRF fusion, reranking, and benchmark runner |
| **Code Quality (20%)** | Clean FastAPI, typed Python, React hooks pattern, service layer |
| **UI/UX (10%)** | Dark glassmorphism, streaming, drag-drop, source highlighting |
| **Deployment (10%)** | Docker Compose + Render Blueprint (`render.yaml`) |
| **Documentation (5%)** | README + evaluation harness docs + generated reports |

---

## 📝 License

MIT License — see [LICENSE](LICENSE)
