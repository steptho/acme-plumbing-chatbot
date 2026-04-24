import streamlit as st
import re
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
from datetime import datetime
import pandas as pd
import os

# --- 1. CONFIGURATION & BANNER ---
st.set_page_config(page_title="ACME Plumbing Dispatch", page_icon="🔧")

st.markdown("""
    <div style="background-color:#0056b3;padding:15px;border-radius:10px;border: 2px solid #004494;">
    <h1 style="color:white;text-align:center;margin:0;">🔧 ACME PLUMBING</h1>
    <p style="color:white;text-align:center;margin:5px 0 0 0;font-weight:bold;">24/7 Emergency Dispatch System</p>
    </div>
    <br>
""", unsafe_allow_html=True)

# --- SAFE SECRET LOADING ---
def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)

# --- OpenAI CLIENT (FIXED) ---
api_key = get_secret("OPENAI_API_KEY")

if not api_key:
    st.error("❌ Missing OPENAI_API_KEY. Set it in environment variables or Streamlit secrets.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- 2. SESSION STATE ---
if "data" not in st.session_state:
    st.session_state.data = {
        "name": None,
        "phone": None,
        "email": None,
        "address": None,
        "issue": None,
        "initial_advice": ""
    }

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "step" not in st.session_state:
    st.session_state.step = "name"

if "work_order_text" not in st.session_state:
    st.session_state.work_order_text = ""

# --- Welcome message ---
if len(st.session_state.chat_history) == 0:
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Hello! I'd love to get a plumber out to you. Could you please start by telling me your **Full Name**?"
    })

# --- 3. FUNCTIONS ---
def get_next_order_number():
    file_name = "order_number.txt"
    if not os.path.exists(file_name):
        with open(file_name, "w") as f:
            f.write("1000")
        return 1000

    with open(file_name, "r") as f:
        current_no = int(f.read().strip())

    next_no = current_no + 1

    with open(file_name, "w") as f:
        f.write(str(next_no))

    return next_no


def log_to_csv(data):
    try:
        file_name = "acme_leads.csv"

        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df = pd.DataFrame([data])

        if not os.path.isfile(file_name):
            df.to_csv(file_name, index=False)
        else:
            df.to_csv(file_name, mode='a', header=False, index=False)

    except Exception as e:
        st.error(f"Logging failed: {e}")


def format_work_order_text(data):
    return f"""
==================================================
           ACME PLUMBING - OFFICIAL WORK ORDER
==================================================
WORK ORDER ID: {data.get('order_number','PENDING')}
DATE: {datetime.now().strftime("%Y-%m-%d")}
--------------------------------------------------
CUSTOMER:
{data['name']} | {data['phone']} | {data['email']}

ADDRESS:
{data['address']}

ISSUE:
{data['issue']}
--------------------------------------------------
ADVICE:
{data['initial_advice']}
==================================================
"""


def send_work_order_email(data, email_body):
    try:
        sender = get_secret("MAIL_USERNAME")
        password = get_secret("MAIL_PASSWORD")

        if not sender or not password:
            return "Missing email credentials"

        msg = MIMEText(email_body)
        msg['Subject'] = f"URGENT: Work Order {data['order_number']} - {data['name']}"
        msg['From'] = sender
        msg['To'] = data['email']

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        return True

    except Exception as e:
        return str(e)

# --- 4. DISPLAY CHAT ---
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. CHAT LOGIC ---
if prompt := st.chat_input("Enter details..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    reply = ""

    # STEP 1: NAME
    if st.session_state.step == "name":
        if len(prompt.split()) < 2:
            reply = "Please enter your full name."
        else:
            st.session_state.data["name"] = prompt
            st.session_state.step = "phone"
            reply = "Thanks. What is your phone number?"

    # STEP 2: PHONE
    elif st.session_state.step == "phone":
        st.session_state.data["phone"] = prompt
        st.session_state.step = "email"
        reply = "What is your email address?"

    # STEP 3: EMAIL
    elif st.session_state.step == "email":
        if re.match(r'^[^@]+@[^@]+\.[^@]+$', prompt):
            st.session_state.data["email"] = prompt
            st.session_state.step = "address"
            reply = "What is the full address?"
        else:
            reply = "Please enter a valid email address."

    # STEP 4: ADDRESS
    elif st.session_state.step == "address":
        st.session_state.data["address"] = prompt
        st.session_state.step = "issue"
        reply = "What is the plumbing issue?"

    # STEP 5: ISSUE + FINAL
    elif st.session_state.step == "issue":
        st.session_state.data["issue"] = prompt

        with st.spinner("Finalising work order..."):
            order_no = get_next_order_number()
            st.session_state.data["order_number"] = order_no

            advice = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"Give 3 short safety tips for: {prompt}"
                }]
            )

            st.session_state.data["initial_advice"] = advice.choices[0].message.content

            log_to_csv(st.session_state.data.copy())

            work_order = format_work_order_text(st.session_state.data)
            st.session_state.work_order_text = work_order

            email_status = send_work_order_email(st.session_state.data, work_order)

            if email_status is True:
                reply = f"✅ Dispatch Confirmed! Work order #{order_no} sent."
            else:
                reply = f"Saved order #{order_no}, email failed: {email_status}"

        st.session_state.step = "complete"

    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    st.rerun()

# --- 6. OUTPUT ---
if st.session_state.step == "complete":
    st.divider()
    st.text(st.session_state.work_order_text)

# --- 7. SIDEBAR ---
with st.sidebar:
    st.header("Admin Tools")

    if st.button("Reset Bot"):
        st.session_state.clear()
        st.rerun()

    if os.path.exists("acme_leads.csv"):
        with open("acme_leads.csv", "rb") as f:
            st.download_button("Download Leads CSV", f, "acme_leads.csv")