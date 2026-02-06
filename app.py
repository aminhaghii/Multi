import os
# جلوگیری از بارگذاری TensorFlow توسط transformers (نیازی نداریم)
os.environ["TRANSFORMERS_NO_TF"] = "1"

import streamlit as st
from main_engine import Orchestrator
from llm_client import LLMClient
from vector_store import VectorStore
from ingestion import DocumentProcessor
from image_captioner import ImageCaptioner
from pathlib import Path

st.set_page_config(
    page_title="Agentic Research Assistant",
    page_icon=None,
    layout="wide"
)

# BUG-027 FIX: Remove @st.cache_resource to prevent data leak between users
# Use session_state for per-user isolation
def initialize_system():
    # Check if already initialized in this session
    if 'vector_store' in st.session_state:
        return (
            st.session_state.llm_client,
            st.session_state.vector_store,
            st.session_state.processor,
            st.session_state.orchestrator
        )
    
    # Initialize fresh for this user session
    llm_client = LLMClient(base_url="http://127.0.0.1:8080")
    vector_store = VectorStore(persist_directory="./faiss_db")
    processor = DocumentProcessor(vector_store, chunk_size=500, chunk_overlap=50)
    
    try:
        image_captioner = ImageCaptioner()
    except Exception as e:
        print(f"Warning: Could not load image captioner: {e}")
        image_captioner = None
    
    orchestrator = Orchestrator(
        llm_client=llm_client,
        vector_store=vector_store,
        image_captioner=image_captioner,
        max_refinement_iterations=2,
        confidence_threshold=0.7
    )
    
    # Store in session state for this user only
    st.session_state.llm_client = llm_client
    st.session_state.vector_store = vector_store
    st.session_state.processor = processor
    st.session_state.orchestrator = orchestrator
    
    return llm_client, vector_store, processor, orchestrator

st.title("Agentic Research Assistant")
st.markdown("---")

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

llm_client, vector_store, processor, orchestrator = initialize_system()

with st.sidebar:
    st.header("System Status")
    
    server_healthy = llm_client.health_check()
    if server_healthy:
        st.success("LLM Server: Online")
    else:
        st.error("LLM Server: Offline")
        st.warning("Please start the model server first!")
    
    multimodal_healthy = llm_client.multimodal_health_check()
    if multimodal_healthy:
        st.success("Multimodal Server: Online")
    else:
        st.info("Multimodal Server: Offline (using caption fallback)")
    
    doc_count = vector_store.get_collection_count()
    st.info(f"Documents in KB: {doc_count}")
    
    st.markdown("---")
    st.header("Knowledge Base Management")
    
    if st.button("Clear All Documents"):
        import shutil
        if os.path.exists("./faiss_db"):
            shutil.rmtree("./faiss_db")
        st.success("Knowledge base cleared")
        st.rerun()
    
    st.markdown("---")
    st.header("Upload Documents")
    
    upload_type = st.radio("Upload Type:", ["PDF", "Image", "Voice"], horizontal=True)
    
    if upload_type == "PDF":
        uploaded_file = st.file_uploader(
            "Upload PDF to Knowledge Base",
            type=['pdf'],
            help="Upload a PDF file to add to the knowledge base"
        )
        
        if uploaded_file is not None:
            if st.button("Process PDF"):
                with st.spinner("Processing PDF..."):
                    temp_path = f"./data/{uploaded_file.name}"
                    os.makedirs("./data", exist_ok=True)
                    
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getvalue())
                    
                    try:
                        result = processor.process_pdf(temp_path)
                        st.success(f"Processed: {result['num_chunks']} chunks from {result['num_pages']} pages")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        # BUG-026 FIX: Clean up temp file
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
    
    elif upload_type == "Image":
        uploaded_image = st.file_uploader(
            "Upload Image",
            type=['png', 'jpg', 'jpeg'],
            help="Upload an image to add to knowledge base with caption"
        )
        
        if uploaded_image is not None:
            st.image(uploaded_image, caption="Uploaded Image", use_column_width=True)
            
            if st.button("Process Image"):
                with st.spinner("Captioning image..."):
                    os.makedirs("./data", exist_ok=True)
                    img_path = f"./data/{uploaded_image.name}"
                    
                    with open(img_path, "wb") as f:
                        f.write(uploaded_image.getvalue())
                    
                    try:
                        from image_captioner import ImageCaptioner
                        captioner = ImageCaptioner()
                        caption = captioner.caption_image(img_path)
                        
                        text_with_caption = f"Image: {uploaded_image.name}\nCaption: {caption}"
                        
                        import hashlib
                        file_hash = hashlib.md5(uploaded_image.getvalue()).hexdigest()[:8]
                        
                        metadata = {
                            "source": img_path,
                            "page": 0,
                            "chunk_index": 0,
                            "file_hash": file_hash,
                            "images": img_path
                        }
                        
                        vector_store.add_documents([text_with_caption], [metadata], [file_hash])
                        
                        st.success(f"Image processed and added with caption: {caption[:100]}...")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        # BUG-026 FIX: Clean up temp file
                        if os.path.exists(img_path):
                            os.remove(img_path)
    
    elif upload_type == "Voice":
        uploaded_audio = st.file_uploader(
            "Upload Audio",
            type=['wav', 'mp3', 'm4a', 'ogg'],
            help="Upload audio file to transcribe and store in knowledge base"
        )
        
        if uploaded_audio is not None:
            if st.button("Transcribe & Save to KB"):
                with st.spinner("Transcribing audio..."):
                    os.makedirs("./data", exist_ok=True)
                    audio_path = f"./data/{uploaded_audio.name}"
                    
                    with open(audio_path, "wb") as f:
                        f.write(uploaded_audio.getvalue())
                    
                    try:
                        from voice_transcriber import VoiceTranscriber
                        transcriber = VoiceTranscriber(model_size="tiny")
                        transcription = transcriber.transcribe(audio_path)
                        
                        if transcription and not transcription.startswith("Error"):
                            text_with_transcription = f"Audio: {uploaded_audio.name}\nTranscription: {transcription}"
                            
                            import hashlib
                            file_hash = hashlib.md5(uploaded_audio.getvalue()).hexdigest()[:8]
                            
                            metadata = {
                                "source": audio_path,
                                "page": 0,
                                "chunk_index": 0,
                                "file_hash": file_hash,
                                "images": ""
                            }
                            
                            vector_store.add_documents([text_with_transcription], [metadata], [file_hash])
                            
                            st.success(f"Audio transcribed and saved to KB: {transcription[:100]}...")
                            st.rerun()
                        else:
                            st.error(transcription)
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        # BUG-026 FIX: Clean up temp file
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
    
    st.markdown("---")
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

st.header("Chat Interface")

if not server_healthy:
    st.warning("LLM Server is not running. Please start it to use the assistant.")
elif doc_count == 0:
    st.info("No documents in knowledge base. Upload a PDF to get started.")

# نمایش تاریخچه مکالمه
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "metadata" in message:
            st.json(message["metadata"])

# ورودی چت باید بیرون از هر expander/columns باشد
user_query = st.chat_input("Ask a question about your documents...", disabled=not server_healthy)

if user_query:
    # BUG-023 FIX: Use copy to prevent race condition between browser tabs
    new_history = st.session_state.chat_history.copy()
    new_history.append({
        "role": "user",
        "content": user_query
    })
    st.session_state.chat_history = new_history
    
    with st.chat_message("user"):
        st.markdown(user_query)
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = orchestrator.run_query(user_query)
            
            if result['success']:
                st.markdown(result['answer'])
                
                metadata = {
                    "Confidence": f"{result['confidence']:.2f}",
                    "Verified": "Yes" if result['verified'] else "No",
                    "Iterations": result['num_iterations'],
                    "Sources Used": result['num_sources']
                }
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Confidence", f"{result['confidence']:.0%}")
                col2.metric("Verified", "Yes" if result['verified'] else "No")
                col3.metric("Iterations", result['num_iterations'])
                col4.metric("Sources", result['num_sources'])
                
                # BUG-023 FIX: Use copy to prevent race condition
                new_history = st.session_state.chat_history.copy()
                new_history.append({
                    "role": "assistant",
                    "content": result['answer'],
                    "metadata": metadata
                })
                st.session_state.chat_history = new_history
            else:
                error_msg = f"Error: {result.get('error', 'Unknown error')}"
                st.error(error_msg)
                # BUG-023 FIX: Use copy to prevent race condition
                new_history = st.session_state.chat_history.copy()
                new_history.append({
                    "role": "assistant",
                    "content": error_msg
                })
                st.session_state.chat_history = new_history

st.markdown("---")

st.subheader("System Execution Logs")
if st.session_state.chat_history and hasattr(orchestrator, 'execution_log') and orchestrator.execution_log:
    for log_entry in orchestrator.execution_log:
        st.text(f"Step: {log_entry['step']}")
        st.json(log_entry['details'])
        st.markdown("---")
else:
    st.info("No logs available. Execute a query first.")

st.markdown("---")
st.caption("Agentic Research Assistant | Powered by MiMo-VL-7B")
