# 📄 DocLens v2 — Intelligent Document Analysis

DocLens is a RAG-powered document analysis tool. Ask questions about any PDF and get intelligent, context-aware answers powered by Groq's LLaMA model.

---

## 🆕 What's New in v2

| Feature | v1 | v2 |
|---|---|---|
| Retrieval algorithm | TF-IDF | **BM25** (more accurate) |
| Chunking | Character-boundary | **Sentence-aware** (no mid-sentence cuts) |
| PDF input | URL only | **URL or file upload** |
| Prompting | Direct Q&A | **Chain-of-thought with page citations** |
| Answer quality | Good | **Better — grounded with citations** |

---

## 🏗️ Architecture

```
[Streamlit Frontend]  ──►  [FastAPI Backend on Vercel]  ──►  [Groq LLM API]
  (Streamlit Cloud)              (Serverless)
```

---

## 🚀 Deployment Guide

### Step 1 — Deploy Backend to Vercel

1. Push this project to a GitHub repository
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → import your repo
3. In the Vercel dashboard, go to **Settings → Environment Variables** and add:
   - `GROQ_API_KEY` → your key from [groq.com](https://console.groq.com)
4. Click **Deploy**
5. Note your backend URL: `https://your-project.vercel.app`

### Step 2 — Deploy Frontend to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account and select this repo
3. Set **Main file path** to: `streamlit_app.py`
4. Under **Advanced settings → Secrets**, add:
   ```
   BACKEND_DOCLENS_API_URL = "https://your-project.vercel.app/DocLens"
   ```
5. Click **Deploy**

---

## 🛠️ Local Development

```bash
# Install backend deps
pip install -r requirements.txt

# Create .env from example
cp .env.example .env
# Fill in GROQ_API_KEY in .env

# Terminal 1 - Backend
python main.py

# Terminal 2 - Frontend
streamlit run streamlit_app.py
```

---

## 📊 API Reference

### `POST /DocLens` — URL mode
```json
{
  "documents": "https://example.com/file.pdf",
  "questions": ["What is the coverage limit?", "What are exclusions?"]
}
```

### `POST /DocLens/upload` — File upload mode (new in v2)
```
Content-Type: multipart/form-data
  file: <PDF binary>
  questions: ["What is the coverage limit?"]   ← JSON-encoded array
```

**Both endpoints respond with:**
```json
{
  "answers": ["The coverage limit is ... [Page 4]", "Exclusions include ..."]
}
```

### `GET /health`
Returns `{"status": "healthy"}`.

---

## ⚠️ Vercel Limitations

- **60s max timeout** on Pro plan (10s on Hobby) — large PDFs may time out
- **No persistent storage** — each request is stateless
- **File upload size** — Vercel limits request body to ~4.5 MB on Hobby; use URL mode for larger PDFs

---

## 🔍 How It Works

1. PDF is ingested from URL or direct upload
2. Text is split at sentence boundaries (prevents mid-sentence cuts)
3. **BM25** retrieval finds the top 5 most relevant chunks per question (length-normalised, more accurate than TF-IDF)
4. Chain-of-thought prompting guides Groq's `llama-3.1-8b-instant` to reason before answering
5. Answers include page citations (e.g. `[Page 3]`) when available
