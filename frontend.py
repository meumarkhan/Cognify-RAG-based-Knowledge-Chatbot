import streamlit as st
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Load backend API URL from env
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="RAG Chatbot", page_icon="🤖", layout="wide")

st.title("🤖 RAG Chatbot")
st.write("Ask questions based on your uploaded PDFs.")

# --- Initialize session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    try:
        res = requests.get(f"{BACKEND_URL}/api/v1/all-chats")
        if res.status_code == 200:
            chats = res.json().get("chats", [])
            # API gives reverse order → reverse again to chronological
            
            for entry in chats:
                st.session_state.chat_history.append((entry["role"], entry["message"]))
    except Exception as e:
        st.warning(f"⚠️ Could not load chat history: {e}")

# --- Sidebar: Upload and new session ---
st.sidebar.header("Upload PDF")
uploaded_file = st.sidebar.file_uploader("Choose a PDF", type="pdf")

if uploaded_file:
    st.sidebar.success(f"Uploaded: {uploaded_file.name}")
    files = {"file": uploaded_file}
    res = requests.post(f"{BACKEND_URL}/api/v1/upload", files=files)
    if res.status_code == 200:
        st.sidebar.success("File processed successfully ✅")
    else:
        st.sidebar.error("Failed to upload file ❌")

if st.sidebar.button("🆕 New Session"):
    try:
        res = requests.get(f"{BACKEND_URL}/api/v1/new-session")
        if res.status_code == 200:
            st.session_state.chat_history = []
            st.sidebar.success("New session started ✅")
        else:
            st.sidebar.error("Failed to reset session ❌")
    except Exception as e:
        st.sidebar.error(f"⚠️ {e}")

# --- Display chat messages ---
for role, msg in st.session_state.chat_history:
    if role.lower() in ["user", "you"]:
        with st.chat_message("user"):  # right aligned
            st.markdown(msg)
    else:
        with st.chat_message("assistant"):  # left aligned
            st.markdown(msg)

# --- Chat input at bottom ---
st.divider()
col1, col2 = st.columns([5, 1])

with col1:
    user_query = st.text_input("Type your message...", key="user_input", label_visibility="collapsed")

with col2:
    send_clicked = st.button("Send", use_container_width=True)

# --- Handle send ---
if send_clicked and user_query:
    payload = {"query": user_query}
    try:
        res = requests.post(f"{BACKEND_URL}/api/v1/query", json=payload)
        if res.status_code == 200:
            data = res.json()
            request_id = data.get("request_id")

            # Add user message immediately
            st.session_state.chat_history.append(("user", user_query))

            # Poll for response
            answer = None
            with st.spinner("🤖 Thinking..."):
                for _ in range(60):  # poll up to ~60s
                    poll = requests.get(f"{BACKEND_URL}/api/v1/query-result/{request_id}")
                    if poll.status_code == 200:
                        poll_data = poll.json()
                        if poll_data["status"] == "done":
                            answer = poll_data["answer"]
                            break
                    time.sleep(1)  # wait 1s before next poll

            if answer:
                st.session_state.chat_history.append(("assistant", answer))
            else:
                st.session_state.chat_history.append(("assistant", "⚠️ Timeout, no response yet."))

            st.rerun()
        else:
            st.error("Backend error")
    except Exception as e:
        st.error(f"Request failed: {e}")
