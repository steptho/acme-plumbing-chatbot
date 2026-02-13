# web_chatbot.py
import os
import streamlit as st
from openai import OpenAI
import PyPDF2
import pandas as pd

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="Steve's Chatbot",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Steve's Chatbot")

# -----------------------------
# OpenAI Client
# -----------------------------
# Use environment variables or Streamlit secrets
api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
org_id = os.getenv("OPENAI_ORG_ID") or st.secrets.get("OPENAI_ORG_ID")
project_id = os.getenv("OPENAI_PROJECT_ID") or st.secrets.get("OPENAI_PROJECT_ID")

if not api_key or not org_id or not project_id:
    st.error(
        "API Key, Organization ID, or Project ID not set! "
        "Please set OPENAI_API_KEY, OPENAI_ORG_ID, and OPENAI_PROJECT_ID."
    )
    st.stop()

client = OpenAI(
    api_key=api_key,
    organization=org_id,
)

# -----------------------------
# Session Memory
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -----------------------------
# File Upload
# -----------------------------
uploaded_file = st.file_uploader("Upload PDF or CSV", type=["pdf", "csv"])

file_text = ""
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        for page in pdf_reader.pages:
            file_text += page.extract_text() + "\n"
    elif uploaded_file.type == "text/csv":
        df = pd.read_csv(uploaded_file)
        file_text = df.to_string(index=False)
    
    # Add file content as system message
    st.session_state.messages.append({
        "role": "system",
        "content": file_text
    })
    st.success(f"Loaded {uploaded_file.name} into conversation.")

# -----------------------------
# User Input
# -----------------------------
if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state.messages
        )
        reply = response.choices[0].message.content

        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

    except Exception as e:
        st.error(f"Error: {e}")



