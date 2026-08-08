"""
AI Video Assistant — Streamlit UI
 
Thin UI layer over the existing core/ and utlis/ pipeline (the same
functions main.py's CLI uses). Turns a YouTube link or local file into
a transcript, summary, action items, key decisions, open questions,
and a chat you can ask follow-up questions to.
"""
 
import os
import tempfile
import uuid
 
import streamlit as st
from dotenv import load_dotenv
 
from utlis.audio_processor import process_input
from core.transcriber import transcribe_all
from core.Summarize import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question
 
load_dotenv()
 
st.set_page_config(
    page_title="AI Video Assistant",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# -- Fonts + light polish --------------------------------------------
# Fraunces for headings (a document/minutes feel), IBM Plex Sans for
# body text, IBM Plex Mono for transcript/code-like content.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
 
    html, body, p, li, div, span, [data-testid="stMarkdownContainer"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    h1, h2, h3, h4, [data-testid="stHeading"] {
        font-family: 'Fraunces', serif !important;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    code, pre, .stCodeBlock, [data-testid="stChatInput"] textarea {
        font-family: 'IBM Plex Mono', monospace !important;
    }
    .stApp { background-color: #F6F7F5; }
    [data-testid="stSidebar"] { background-color: #EAEBE6; }
    [data-testid="stMetricValue"] { font-family: 'Fraunces', serif; }
 
    .avassist-stage {
        display: flex; align-items: center; gap: 0.6rem;
        padding: 0.55rem 0.9rem; border-radius: 8px;
        background: #EAEBE6; margin-bottom: 0.4rem;
        font-size: 0.92rem; color: #20242E;
    }
    .avassist-stage .num {
        font-family: 'Fraunces', serif; font-weight: 600;
        color: #B8862E; min-width: 1.2rem;
    }
    .avassist-empty {
        border: 1px dashed #C9CBC3; border-radius: 10px;
        padding: 2rem; text-align: center; color: #55594F;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
 
# -- Session state -----------------------------------------------------
defaults = {
    "pipeline_result": None,
    "chat_messages": [],
    "collection_name": None,
    "last_error": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value
 
ACCEPTED_TYPES = ["mp3", "wav", "m4a", "aac", "flac", "ogg", "mp4", "mov", "mkv", "webm", "avi"]
 
 
def run_pipeline_ui(source: str, language: str, collection_name: str):
    """Run the same pipeline main.py's CLI runs, with per-stage status
    updates and errors surfaced in the UI instead of a stack trace."""
    try:
        with st.status("Processing your video...", expanded=True) as status:
            status.write("🎧 Preparing audio (downloading / converting / chunking)...")
            chunks = process_input(source)
 
            engine = "Sarvam AI" if language == "hinglish" else "Whisper"
            status.write(f"📝 Transcribing with {engine}...")
            transcript = transcribe_all(chunks, language)
 
            status.write("🏷️ Generating title...")
            title = generate_title(transcript)
 
            status.write("📋 Summarizing (map-reduce)...")
            summary = summarize(transcript)
 
            status.write("✅ Extracting action items...")
            action_items = extract_action_items(transcript)
 
            status.write("🔑 Extracting key decisions...")
            decisions = extract_key_decisions(transcript)
 
            status.write("❓ Extracting open questions...")
            questions = extract_questions(transcript)
 
            status.write("💬 Building chat index...")
            rag_chain = build_rag_chain(transcript, collection_name=collection_name)
 
            status.update(label="Done", state="complete", expanded=False)
 
        return {
            "title": title,
            "transcript": transcript,
            "summary": summary,
            "action_items": action_items,
            "key_decisions": decisions,
            "open_questions": questions,
            "rag_chain": rag_chain,
        }
    except Exception as e:
        st.error(f"Processing failed at some stage of the pipeline: {e}")
        return None
 
 
# -- Sidebar -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎥 New video")
 
    input_mode = st.radio("Source", ["YouTube URL", "Upload a file"], label_visibility="collapsed")
 
    source_url, uploaded_file = None, None
    if input_mode == "YouTube URL":
        source_url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
    else:
        uploaded_file = st.file_uploader("Audio or video file", type=ACCEPTED_TYPES)
 
    language_label = st.selectbox("Language", ["English", "Hinglish"])
    language = language_label.lower()
 
    mistral_ok = bool(os.getenv("MISTRAL_API_KEY"))
    sarvam_ok = bool(os.getenv("SARVAM_API_KEY"))
 
    if not mistral_ok:
        st.warning("MISTRAL_API_KEY is not set - add it to your .env file.", icon="⚠️")
    if language == "hinglish" and not sarvam_ok:
        st.warning("SARVAM_API_KEY is not set - needed for Hinglish transcription.", icon="⚠️")
 
    can_process = mistral_ok and (language != "hinglish" or sarvam_ok)
    has_source = bool(source_url) or uploaded_file is not None
 
    process_clicked = st.button(
        "Process video", type="primary", use_container_width=True,
        disabled=not can_process,
    )
 
    if st.session_state.pipeline_result is not None:
        st.divider()
        if st.button("🔄 Start over", use_container_width=True):
            st.session_state.pipeline_result = None
            st.session_state.chat_messages = []
            st.session_state.collection_name = None
            st.rerun()
 
# -- Handle the Process click ---------------------------------------------
if process_clicked:
    if not has_source:
        st.error("Enter a YouTube URL or upload a file first.")
    else:
        temp_path = None
        try:
            if uploaded_file is not None:
                suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    temp_path = tmp.name
                source = temp_path
            else:
                source = source_url.strip()
 
            # Fresh, isolated vector-store collection per processed video so
            # chat on this video never pulls in chunks from a previous one.
            collection_name = f"session_{uuid.uuid4().hex[:10]}"
 
            st.session_state.chat_messages = []
            result = run_pipeline_ui(source, language, collection_name)
 
            if result is not None:
                st.session_state.pipeline_result = result
                st.session_state.collection_name = collection_name
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
 
# -- Main area --------------------------------------------------------------
st.markdown("# AI Video Assistant")
st.caption("Turn a video or recording into a transcript, a structured summary, and a chat you can ask questions to.")
 
result = st.session_state.pipeline_result
 
if result is None:
    st.markdown(
        """
        <div class="avassist-empty">
        Add a YouTube URL or upload a file in the sidebar, then click <b>Process video</b>.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    stages = [
        ("1", "Audio extraction & chunking"),
        ("2", "Transcription (Whisper / Sarvam AI)"),
        ("3", "Title, summary & extraction"),
        ("4", "Chat index (RAG)"),
    ]
    cols = st.columns(len(stages))
    for col, (num, label) in zip(cols, stages, strict=True):
        with col:
            st.markdown(
                f'<div class="avassist-stage"><span class="num">{num}</span>{label}</div>',
                unsafe_allow_html=True,
            )
else:
    st.markdown(f"## {result['title']}")
 
    tab_summary, tab_actions, tab_decisions, tab_questions, tab_transcript = st.tabs(
        ["📋 Summary", "✅ Action Items", "🔑 Key Decisions", "❓ Open Questions", "📝 Transcript"]
    )
    with tab_summary:
        st.markdown(result["summary"])
    with tab_actions:
        st.markdown(result["action_items"])
    with tab_decisions:
        st.markdown(result["key_decisions"])
    with tab_questions:
        st.markdown(result["open_questions"])
    with tab_transcript:
        st.text_area("Full transcript", result["transcript"], height=300, label_visibility="collapsed")
 
    minutes_doc = (
        f"# {result['title']}\n\n"
        f"## Summary\n{result['summary']}\n\n"
        f"## Action Items\n{result['action_items']}\n\n"
        f"## Key Decisions\n{result['key_decisions']}\n\n"
        f"## Open Questions\n{result['open_questions']}\n"
    )
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "⬇️ Download meeting minutes (.md)", minutes_doc,
            file_name="meeting_minutes.md", use_container_width=True,
        )
    with dl2:
        st.download_button(
            "⬇️ Download full transcript (.txt)", result["transcript"],
            file_name="transcript.txt", use_container_width=True,
        )
 
    st.divider()
    st.markdown("### 💬 Chat with your meeting")
 
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
 
    question = st.chat_input("Ask something about this meeting...")
    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = ask_question(result["rag_chain"], question)
                except Exception as e:
                    answer = f"Sorry, I hit an error answering that: {e}"
            st.markdown(answer)
        st.session_state.chat_messages.append({"role": "assistant", "content": answer})
 
