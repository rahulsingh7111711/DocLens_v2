import streamlit as st
import requests
from urllib.parse import urlparse
import os
import json
import base64
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="DocLens — Document Intelligence",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Source+Sans+3:wght@300;400;500;600&family=Courier+Prime:wght@400;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background: #F2EDE4 !important;
    font-family: 'Source Sans 3', sans-serif !important;
    color: #2C2416 !important;
}

#MainMenu, footer, header { visibility: hidden !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }

section[data-testid="stSidebar"] { background: #2C2416 !important; }
section[data-testid="stSidebar"] * { color: #E8DFD0 !important; font-family: 'Source Sans 3', sans-serif !important; }
section[data-testid="stSidebar"] .stTextInput input {
    background: #3D3020 !important; color: #E8DFD0 !important;
    border: 1px solid #5C4A30 !important; border-radius: 6px !important;
}
section[data-testid="stSidebar"] label {
    color: #8A7560 !important; font-size: 0.7rem !important;
    letter-spacing: 0.1em !important; text-transform: uppercase !important;
    font-family: 'Courier Prime', monospace !important;
}

.stTextInput input {
    background: #FDF8F0 !important;
    border: 1.5px solid #D4C4A8 !important;
    border-radius: 8px !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.92rem !important;
    color: #2C2416 !important;
    padding: 0.6rem 1rem !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput input:focus {
    border-color: #8B6914 !important;
    box-shadow: 0 0 0 3px rgba(139,105,20,0.1) !important;
}
.stTextInput label {
    font-family: 'Courier Prime', monospace !important;
    font-size: 0.62rem !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: #8A7560 !important;
}

.stButton > button {
    font-family: 'Source Sans 3', sans-serif !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    transition: all 0.18s !important;
}
.stButton > button[kind="primary"] {
    background: #2C2416 !important;
    color: #F2EDE4 !important;
    border: none !important;
    padding: 0.65rem 2rem !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.03em !important;
}
.stButton > button[kind="primary"]:hover {
    background: #4A3820 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 18px rgba(44,36,22,0.18) !important;
}
.stButton > button:not([kind="primary"]) {
    background: transparent !important;
    border: 1.5px solid #C9B898 !important;
    color: #6B5740 !important;
    font-size: 0.8rem !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #2C2416 !important;
    color: #2C2416 !important;
    background: #EDE6D8 !important;
}

.stFileUploader > div {
    border: 2px dashed #C9B898 !important;
    border-radius: 10px !important;
    background: #FDF8F0 !important;
    transition: border-color 0.2s !important;
}
.stFileUploader > div:hover { border-color: #8B6914 !important; }

.stRadio > div { gap: 0 !important; }
.stRadio label { font-size: 0.87rem !important; font-family: 'Source Sans 3', sans-serif !important; color: #2C2416 !important; }

.stAlert { border-radius: 8px !important; font-size: 0.84rem !important; font-family: 'Source Sans 3', sans-serif !important; }
.streamlit-expanderHeader { font-family: 'Source Sans 3', sans-serif !important; font-size: 0.85rem !important; color: #2C2416 !important; }
.streamlit-expanderContent { background: #FDF8F0 !important; border-radius: 0 0 10px 10px !important; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #EDE6D8; }
::-webkit-scrollbar-thumb { background: #C9B898; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [('questions', [""]), ('answers', []), ('processing', False),
              ('pdf_url', ''), ('pdf_preview_b64', None), ('pdf_filename', '')]:
    if k not in st.session_state:
        st.session_state[k] = v

def validate_url(url):
    try:
        r = urlparse(url)
        return all([r.scheme, r.netloc])
    except:
        return False

def is_pdf_url(url):
    return url.lower().endswith('.pdf') or 'pdf' in url.lower()

def add_question():
    if len(st.session_state.questions) < 10:
        st.session_state.questions.append("")

def remove_question(i):
    if len(st.session_state.questions) > 1:
        st.session_state.questions.pop(i)
        st.rerun()

def get_api_url():
    return os.getenv("BACKEND_DOCLENS_API_URL", "http://localhost:8000/DocLens")

def process_url():
    valid_qs = [q.strip() for q in st.session_state.questions if q.strip()]
    if not st.session_state.pdf_url.strip():
        st.error("Please enter a PDF URL.")
        return
    if not valid_qs:
        st.error("Add at least one question.")
        return
    if not validate_url(st.session_state.pdf_url):
        st.error("Invalid URL format.")
        return
    st.session_state.processing = True
    try:
        with st.spinner("Reading document and forming answers…"):
            r = requests.post(get_api_url(),
                              json={"documents": st.session_state.pdf_url.strip(),
                                    "questions": valid_qs},
                              timeout=120)
        if r.status_code == 200:
            st.session_state.answers = r.json().get('answers', [])
        else:
            st.error(r.json().get('detail', 'Unknown error'))
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")
    finally:
        st.session_state.processing = False

def process_upload(uploaded):
    valid_qs = [q.strip() for q in st.session_state.questions if q.strip()]
    if not valid_qs:
        st.error("Add at least one question.")
        return
    if not uploaded:
        st.error("Upload a PDF first.")
        return
    st.session_state.processing = True
    try:
        upload_url = get_api_url().replace("/DocLens", "") + "/DocLens/upload"
        with st.spinner(f"Uploading and reading {uploaded.name}…"):
            r = requests.post(
                upload_url,
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                data={"questions": json.dumps(valid_qs)},
                timeout=120
            )
        if r.status_code == 200:
            st.session_state.answers = r.json().get('answers', [])
        else:
            st.error(r.json().get('detail', 'Unknown error'))
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")
    finally:
        st.session_state.processing = False


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    backend = st.text_input(
        "Backend URL",
        value=os.getenv("BACKEND_DOCLENS_API_URL", "http://localhost:8000/DocLens")
    )
    if backend:
        os.environ["BACKEND_DOCLENS_API_URL"] = backend
    try:
        hr = requests.get(backend.replace("/DocLens", "") + "/health", timeout=4)
        st.success("Backend connected") if hr.status_code == 200 else st.error("Backend error")
    except:
        st.warning("Backend unreachable")
    st.divider()
    st.caption("DocLens v2.0 · Groq · LLaMA 3.1")


# ── Masthead ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    background: #2C2416;
    padding: 0 0 0 0;
    position: relative;
    overflow: hidden;
">
  <!-- subtle paper grain texture via repeating gradient -->
  <div style="
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 3px,
      rgba(255,255,255,0.015) 3px, rgba(255,255,255,0.015) 4px
    );
    pointer-events: none;
  "></div>

  <!-- top rule bar -->
  <div style="height:3px; background: linear-gradient(90deg, #8B6914 0%, #C4960A 50%, #8B6914 100%);"></div>

  <div style="padding: 1.5rem 3rem 1.25rem; position: relative; z-index:1;">
    <div style="display:flex; align-items:baseline; justify-content:space-between; border-bottom: 1px solid #4A3820; padding-bottom: 0.85rem; margin-bottom: 0.85rem;">
      <div style="display:flex; align-items:baseline; gap: 1.25rem;">
        <span style="font-family:'Lora',serif; font-size: 2rem; font-weight:600; letter-spacing:-0.02em; color:#F2EDE4;">DocLens</span>
        <span style="font-family:'Courier Prime',monospace; font-size:0.6rem; color:#8B6914; letter-spacing:0.15em; text-transform:uppercase;">Est. 2024</span>
      </div>
      <span style="font-family:'Courier Prime',monospace; font-size:0.6rem; color:#5C4A30; letter-spacing:0.1em; text-transform:uppercase;">Vol. II · Intelligent Document Analysis</span>
    </div>
    <div style="text-align:center; padding: 0.5rem 0 0.25rem;">
      <h1 style="font-family:'Lora',serif; font-size:clamp(1.6rem,3.5vw,2.6rem); font-weight:400; font-style:italic; color:#E8DFD0; letter-spacing:-0.01em; line-height:1.2; margin-bottom:0.5rem;">
        Ask anything about any document.
      </h1>
      <p style="font-family:'Source Sans 3',sans-serif; font-size:0.88rem; font-weight:300; color:#8A7560; letter-spacing:0.04em;">
        Upload a PDF or paste a URL · Powered by BM25 retrieval & LLaMA 3.1
      </p>
    </div>
  </div>

  <!-- bottom rule -->
  <div style="height:1px; background:#4A3820;"></div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)

# ── Body ──────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1.1, 1], gap="large")

with col_left:

    # ── Source card ───────────────────────────────────
    st.markdown("""
    <div style="background:#FDF8F0; border:1.5px solid #D4C4A8; border-radius:14px;
         padding:1.6rem 1.75rem 1.25rem; margin-bottom:1rem;
         box-shadow: 2px 3px 12px rgba(44,36,22,0.06);">
    """, unsafe_allow_html=True)

    st.markdown('<p style="font-family:\'Courier Prime\',monospace; font-size:0.6rem; letter-spacing:0.18em; text-transform:uppercase; color:#A08C6E; margin-bottom:0.75rem;">§ 1 — Document Source</p>', unsafe_allow_html=True)

    mode = st.radio("", ["🔗  Paste a URL", "📎  Upload a file"],
                    horizontal=True, label_visibility="collapsed")

    uploaded_file = None
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if mode == "🔗  Paste a URL":
        url_val = st.text_input("PDF URL",
                                placeholder="https://example.com/policy.pdf",
                                label_visibility="collapsed")
        if url_val:
            st.session_state.pdf_url = url_val
            if validate_url(url_val):
                color = "#5C8A4A" if is_pdf_url(url_val) else "#A07030"
                msg   = "✓ PDF URL detected" if is_pdf_url(url_val) else "⚠ URL may not be a PDF — will attempt anyway"
                st.markdown(f'<p style="font-size:0.78rem; color:{color}; margin-top:-0.2rem; font-family:\'Courier Prime\',monospace;">{msg}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="font-size:0.78rem; color:#A03030; margin-top:-0.2rem; font-family:\'Courier Prime\',monospace;">✗ Invalid URL</p>', unsafe_allow_html=True)
    else:
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded_file:
            mb = len(uploaded_file.getvalue()) / 1_048_576
            st.session_state.pdf_filename = uploaded_file.name
            st.session_state.pdf_preview_b64 = base64.b64encode(uploaded_file.getvalue()).decode()
            st.markdown(f'<p style="font-size:0.78rem; color:#5C8A4A; font-family:\'Courier Prime\',monospace;">✓ {uploaded_file.name} · {mb:.1f} MB</p>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── PDF Preview ────────────────────────────────────
    if mode == "🔗  Paste a URL" and st.session_state.pdf_url and validate_url(st.session_state.pdf_url) and is_pdf_url(st.session_state.pdf_url):
        with st.expander("📖  Preview document", expanded=False):
            st.markdown(f"""
            <div style="border-radius:10px; overflow:hidden; border:1.5px solid #D4C4A8; background:#EDE6D8;">
              <iframe src="{st.session_state.pdf_url}#toolbar=0&view=FitH"
                      width="100%" height="500px" style="border:none; display:block;"></iframe>
            </div>
            <p style="font-size:0.7rem; color:#A08C6E; margin-top:0.4rem; text-align:center; font-family:'Courier Prime',monospace;">
              Preview may be restricted by the source server
            </p>
            """, unsafe_allow_html=True)

    if mode == "📎  Upload a file" and st.session_state.pdf_preview_b64:
        with st.expander("📖  Preview uploaded document", expanded=False):
            st.markdown(f"""
            <div style="border-radius:10px; overflow:hidden; border:1.5px solid #D4C4A8; background:#EDE6D8;">
              <iframe src="data:application/pdf;base64,{st.session_state.pdf_preview_b64}#toolbar=0&view=FitH"
                      width="100%" height="500px" style="border:none; display:block;"></iframe>
            </div>
            <p style="font-size:0.7rem; color:#A08C6E; margin-top:0.4rem; text-align:center; font-family:'Courier Prime',monospace;">
              {st.session_state.pdf_filename}
            </p>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    # ── Questions card ─────────────────────────────────
    st.markdown("""
    <div style="background:#FDF8F0; border:1.5px solid #D4C4A8; border-radius:14px;
         padding:1.6rem 1.75rem 1.25rem; box-shadow: 2px 3px 12px rgba(44,36,22,0.06);">
    """, unsafe_allow_html=True)

    st.markdown('<p style="font-family:\'Courier Prime\',monospace; font-size:0.6rem; letter-spacing:0.18em; text-transform:uppercase; color:#A08C6E; margin-bottom:0.75rem;">§ 2 — Your Questions</p>', unsafe_allow_html=True)

    for i, q in enumerate(st.session_state.questions):
        c1, c2 = st.columns([11, 1])
        with c1:
            st.session_state.questions[i] = st.text_input(
                f"q{i}", value=q,
                placeholder=f"Question {i+1} — e.g. What is the grace period?",
                key=f"q_inp_{i}", label_visibility="collapsed"
            )
        with c2:
            if len(st.session_state.questions) > 1:
                if st.button("✕", key=f"rm_{i}", help="Remove"):
                    remove_question(i)

    c_add, c_count = st.columns([3, 1])
    with c_add:
        st.button("＋ Add question", on_click=add_question, disabled=len(st.session_state.questions) >= 10)
    with c_count:
        st.markdown(f'<p style="font-size:0.72rem; color:#B0A090; text-align:right; margin-top:0.4rem; font-family:\'Courier Prime\',monospace;">{len(st.session_state.questions)}/10</p>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── CTA ────────────────────────────────────────────
    disabled = st.session_state.processing
    if mode == "🔗  Paste a URL":
        st.button("Read & Answer →", type="primary", disabled=disabled,
                  use_container_width=True, on_click=process_url)
    else:
        st.button("Upload & Answer →", type="primary",
                  disabled=disabled or uploaded_file is None,
                  use_container_width=True,
                  on_click=lambda: process_upload(uploaded_file) if uploaded_file else None)
        if uploaded_file is None:
            st.caption("Upload a PDF above to enable.")


with col_right:

    # ── Stats ──────────────────────────────────────────
    answered = len(st.session_state.answers)
    total_qs = len([q for q in st.session_state.questions if q.strip()])
    s1, s2, s3 = st.columns(3)
    for col, lbl, val in [(s1, "Questions", str(total_qs)),
                           (s2, "Answered",  str(answered)),
                           (s3, "Source",    "URL" if mode == "🔗  Paste a URL" else "File")]:
        col.markdown(f"""
        <div style="background:#FDF8F0; border:1.5px solid #D4C4A8; border-radius:10px;
             padding:0.85rem 0.75rem; text-align:center; box-shadow:1px 2px 8px rgba(44,36,22,0.05);">
          <div style="font-family:'Courier Prime',monospace; font-size:0.52rem; letter-spacing:0.14em;
               text-transform:uppercase; color:#A08C6E; margin-bottom:0.25rem;">{lbl}</div>
          <div style="font-family:'Lora',serif; font-size:1.55rem; color:#2C2416;">{val}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # ── Results / empty state ──────────────────────────
    if st.session_state.answers:
        st.markdown('<p style="font-family:\'Courier Prime\',monospace; font-size:0.6rem; letter-spacing:0.18em; text-transform:uppercase; color:#A08C6E; margin-bottom:0.75rem;">Findings</p>', unsafe_allow_html=True)

        valid_qs = [q for q in st.session_state.questions if q.strip()]
        for i, (q, a) in enumerate(zip(valid_qs, st.session_state.answers)):
            not_found = "not found" in a.lower()
            left_border = "#C9B898" if not_found else "#8B6914"
            badge_bg    = "#F5EDD8" if not_found else "#EDE6D8"
            badge_color = "#A07030" if not_found else "#5C3D10"
            badge_text  = "Not found" if not_found else "Answered"

            st.markdown(f"""
            <div style="background:#FDF8F0; border:1.5px solid #D4C4A8; border-radius:13px;
                 overflow:hidden; margin-bottom:1rem; box-shadow:2px 3px 10px rgba(44,36,22,0.06);">

              <!-- Question -->
              <div style="padding:0.9rem 1.2rem 0.75rem; border-bottom:1px solid #EDE6D8; display:flex; gap:0.6rem; align-items:flex-start;">
                <span style="font-family:'Courier Prime',monospace; font-size:0.58rem;
                      color:#C9B898; flex-shrink:0; margin-top:0.2rem;">Q{i+1}</span>
                <span style="font-size:0.88rem; font-weight:500; color:#2C2416; line-height:1.4;">{q}</span>
              </div>

              <!-- Answer -->
              <div style="padding:0.9rem 1.2rem; background:#FAF4EB; border-left:4px solid {left_border};">
                <span style="font-size:0.6rem; font-family:'Courier Prime',monospace;
                      background:{badge_bg}; color:{badge_color};
                      padding:0.12rem 0.55rem; border-radius:4px; display:inline-block; margin-bottom:0.45rem;">
                  {badge_text}
                </span>
                <p style="font-size:0.88rem; color:#3D2E18; line-height:1.7; margin:0; font-weight:300;">{a}</p>
              </div>
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📋 Export answers as plain text"):
            valid_qs2 = [q for q in st.session_state.questions if q.strip()]
            all_text = "\n\n".join(f"Q{i+1}: {q}\nA: {a}" for i, (q, a) in enumerate(zip(valid_qs2, st.session_state.answers)))
            st.code(all_text, language=None)

    else:
        # Empty state — editorial pull-quote style
        st.markdown("""
        <div style="background:#FDF8F0; border:1.5px solid #D4C4A8; border-radius:14px;
             padding:3rem 2rem; text-align:center; box-shadow:2px 3px 12px rgba(44,36,22,0.06);">
          <div style="width:48px; height:48px; background:#EDE6D8; border-radius:50%;
               display:flex; align-items:center; justify-content:center;
               margin:0 auto 1.1rem; font-size:1.5rem;">📄</div>
          <p style="font-family:'Lora',serif; font-size:1.15rem; font-style:italic; color:#5C4A30; margin-bottom:0.5rem; line-height:1.4;">
            Your answers will appear here
          </p>
          <p style="font-size:0.8rem; color:#A08C6E; font-weight:300; max-width:240px; margin:0 auto; line-height:1.6;">
            Enter a document and your questions on the left, then click Read & Answer
          </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # ── Tips callout ───────────────────────────────────
    st.markdown("""
    <div style="background:#F5EDD8; border:1.5px solid #D4C4A8; border-radius:12px; padding:1.2rem 1.4rem;">
      <p style="font-family:'Courier Prime',monospace; font-size:0.58rem; letter-spacing:0.16em;
           text-transform:uppercase; color:#8B6914; margin-bottom:0.6rem;">Tips for better results</p>
      <ul style="font-size:0.82rem; color:#5C4A30; line-height:1.75; padding-left:1.1rem; margin:0; font-weight:300;">
        <li>Ask one specific thing per question</li>
        <li>Name the subject — e.g. <em>"What is the <strong>premium payment</strong> grace period?"</em></li>
        <li>For numbers or lists, ask <em>"List all values for…"</em></li>
        <li>If an answer says "not found", try rephrasing</li>
        <li>Maximum 10 questions per document</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── How it works ───────────────────────────────────
    with st.expander("ℹ How DocLens works"):
        steps = [
            ("I", "Ingest", "PDF downloaded from URL or received via upload"),
            ("II", "Chunk", "Text split at sentence boundaries — no broken context"),
            ("III", "Retrieve", "BM25 ranking surfaces the most relevant passages"),
            ("IV", "Generate", "LLaMA 3.1 reasons step-by-step and cites page numbers"),
        ]
        for num, title, desc in steps:
            st.markdown(f"""
            <div style="display:flex; gap:1rem; padding:0.65rem 0; border-bottom:1px solid #EDE6D8; align-items:flex-start;">
              <span style="font-family:'Courier Prime',monospace; font-size:0.62rem; color:#C9B898; flex-shrink:0; min-width:1.5rem; padding-top:0.1rem;">{num}</span>
              <div>
                <div style="font-size:0.83rem; font-weight:600; color:#2C2416; margin-bottom:0.15rem;">{title}</div>
                <div style="font-size:0.77rem; color:#8A7560; line-height:1.5;">{desc}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="border-top:3px solid #8B6914; background:#2C2416; padding:1.25rem 3rem;
     display:flex; justify-content:space-between; align-items:center;">
  <span style="font-family:'Lora',serif; font-size:1rem; color:#E8DFD0; font-style:italic;">DocLens</span>
  <span style="font-family:'Courier Prime',monospace; font-size:0.55rem; color:#5C4A30; letter-spacing:0.12em; text-transform:uppercase;">
    Streamlit · FastAPI · Groq · Free &amp; Open Source
  </span>
</div>
""", unsafe_allow_html=True)
