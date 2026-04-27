from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import os
import logging
import math
import re
from collections import Counter
from dotenv import load_dotenv
import PyPDF2
import requests
import io
from langchain_groq import ChatGroq

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocLens",
    description="API for processing PDF documents and answering questions using RAG",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic Models ----------

class QueryRequest(BaseModel):
    documents: HttpUrl
    questions: List[str]

class QueryResponse(BaseModel):
    answers: List[str]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ---------- Improved BM25-style Retriever ----------

class BM25Retriever:
    """
    BM25 retriever with sentence-aware chunking.
    BM25 outperforms plain TF-IDF by normalising for document length,
    reducing the bias toward longer chunks that contain more term matches.
    """
    K1 = 1.5   # term frequency saturation
    B  = 0.75  # length normalisation

    def __init__(self, text: str, chunk_size: int = 1500, chunk_overlap: int = 150):
        self.chunks = self._sentence_aware_chunk(text, chunk_size, chunk_overlap)
        self.tokenized_chunks = [self._tokenize(c) for c in self.chunks]
        self.df, self.idf, self.avgdl = self._build_index()
        logger.info(f"BM25 index built: {len(self.chunks)} chunks, avgdl={self.avgdl:.0f}")

    def _sentence_aware_chunk(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split at sentence boundaries so chunks never cut mid-sentence."""
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        sentence_endings = re.compile(r'(?<=[.?!])\s+|\n\n+')
        sentences = [s.strip() for s in sentence_endings.split(text) if s.strip()]

        chunks, current, current_len = [], [], 0
        overlap_buf: List[str] = []

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > chunk_size and current:
                chunks.append(" ".join(current))
                overlap_buf = []
                buf_len = 0
                for s in reversed(current):
                    if buf_len + len(s) > overlap:
                        break
                    overlap_buf.insert(0, s)
                    buf_len += len(s)
                current = list(overlap_buf)
                current_len = sum(len(s) for s in current)
            current.append(sent)
            current_len += sent_len

        if current:
            chunks.append(" ".join(current))

        return chunks if chunks else [text]

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-z][a-z0-9]*\b', text.lower())

    def _build_index(self):
        N = len(self.tokenized_chunks)
        avgdl = sum(len(d) for d in self.tokenized_chunks) / max(N, 1)
        df: Counter = Counter()
        for doc in self.tokenized_chunks:
            for tok in set(doc):
                df[tok] += 1
        idf = {
            tok: math.log((N - freq + 0.5) / (freq + 0.5) + 1)
            for tok, freq in df.items()
        }
        return df, idf, avgdl

    def _bm25_score(self, doc_tokens: List[str], query_tokens: List[str]) -> float:
        tf_counter = Counter(doc_tokens)
        dl = len(doc_tokens)
        score = 0.0
        for qt in query_tokens:
            if qt not in self.idf:
                continue
            tf = tf_counter.get(qt, 0)
            numerator = tf * (self.K1 + 1)
            denominator = tf + self.K1 * (1 - self.B + self.B * dl / max(self.avgdl, 1))
            score += self.idf[qt] * (numerator / denominator)
        return score

    def retrieve(self, query: str, top_k: int = 5) -> List[tuple]:
        query_tokens = self._tokenize(query)
        scored = [
            (self.chunks[i], self._bm25_score(doc_tokens, query_tokens))
            for i, doc_tokens in enumerate(self.tokenized_chunks)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        relevant = [(c, s) for c, s in scored if s > 0]
        return relevant[:top_k] if relevant else scored[:top_k]


# ---------- PDF Extraction ----------

def extract_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(f"[Page {page_num + 1}]\n{page_text}")
        return "\n\n".join(pages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")


def extract_pdf_from_url(url: str) -> str:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return extract_pdf_bytes(response.content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {str(e)}")


# ---------- Prompt Construction ----------

def build_prompt(context: str, query: str) -> str:
    system = (
        "You are DocLens, an expert AI assistant for intelligent document analysis "
        "(insurance, legal, HR, compliance, financial).\n\n"
        "Rules:\n"
        "1. Base ALL answers strictly on the provided context. Never fabricate facts.\n"
        "2. Cite the page or section when you find the answer (e.g. '[Page 3]').\n"
        "3. Think step-by-step before writing the final answer.\n"
        "4. Keep the final answer concise: 1-4 sentences unless complexity demands more.\n"
        "5. If the information is not in the context, say exactly: "
        "\"Information not found in document.\"\n"
    )
    return (
        f"{system}\n\n"
        "--- Document Excerpts ---\n"
        f"{context}\n"
        "--- End of Excerpts ---\n\n"
        f"Question: {query}\n\n"
        "Reasoning (brief, internal):\n"
        "<think>Identify the most relevant excerpt. Note numbers, dates, conditions, exceptions.</think>\n\n"
        "Final Answer:"
    )


def clean_answer(raw: str) -> str:
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
    raw = re.sub(r'^(Final Answer\s*:?\s*)', '', raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r'^[AQ]\s*:\s*', '', raw.strip())
    return raw.strip()


def process_pdf_queries(text: str, questions: List[str], groq_api_key: str) -> List[str]:
    if not text.strip():
        raise HTTPException(status_code=400, detail="Extracted PDF text is empty.")

    llm = ChatGroq(
        groq_api_key=groq_api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0.1,
        max_tokens=500,
    )

    retriever = BM25Retriever(text)
    answers = []
    for query in questions:
        relevant_chunks = retriever.retrieve(query, top_k=5)
        context = "\n\n".join(chunk for chunk, _ in relevant_chunks)
        prompt = build_prompt(context, query)
        response = llm.invoke(prompt)
        answers.append(clean_answer(response.content))

    return answers


# ---------- Endpoints ----------

@app.get("/")
async def root():
    return {"status": "healthy", "message": "DocLens v2 is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "DocLens v2 is running"}


@app.post("/DocLens", response_model=QueryResponse)
async def process_document_url(request: QueryRequest):
    """Accept a publicly accessible PDF URL + list of questions."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    if not request.questions:
        raise HTTPException(status_code=400, detail="At least one question is required")
    if len(request.questions) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 questions per request")

    logger.info("URL mode: %s questions for %s", len(request.questions), request.documents)
    text = extract_pdf_from_url(str(request.documents))
    answers = process_pdf_queries(text, request.questions, groq_api_key)
    return QueryResponse(answers=answers)


@app.post("/DocLens/upload", response_model=QueryResponse)
async def process_document_upload(
    file: UploadFile = File(...),
    questions: str = Form(...),
):
    """Accept a PDF file upload + JSON-encoded list of questions."""
    import json

    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        questions_list: List[str] = json.loads(questions)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="'questions' must be a JSON array of strings.")

    if not questions_list:
        raise HTTPException(status_code=400, detail="At least one question is required.")
    if len(questions_list) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 questions per request.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large (max 20 MB).")

    logger.info("Upload mode: %s questions, file=%s (%d bytes)",
                len(questions_list), file.filename, len(pdf_bytes))

    text = extract_pdf_bytes(pdf_bytes)
    answers = process_pdf_queries(text, questions_list, groq_api_key)
    return QueryResponse(answers=answers)


# ---------- Error Handlers ----------

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY environment variable is required")
        exit(1)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
