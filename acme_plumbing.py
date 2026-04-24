import streamlit as st
import re
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
from datetime import datetime
import pandas as pd
import os

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="ACME Plumbing Dispatch", page_icon="🔧")

st.markdown("""
    <div style="background-color:#0056b3;padding:15px;border-radius:10px;border: 2px solid #004494;">
    <h1 style="color:white;text-align:center;margin:0;">🔧 ACME PLUMBING</h1>
    <p style="color:white;text-align:center;margin:5px 0 0 0;font-weight:bold;">
    24/7 Emergency Dispatch System</p>
    </div>
    <br>
""", unsafe_allow_html=True)

# ----------------------------
# API KEY (FIXED - LOCAL ONLY)
# ----------------------------
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("❌ Missing OPENAI_API_KEY. Set it in Windows environment variables.")
    st.stop()

client = OpenAI(api_key=api_key)

# ----------------------------
# SESSION STATE
# ----------------------------
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

# ----------------------------
# WELCOME MESSAGE
# ----------------------------
if len(st.session_state.chat_history) == 0:
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "Hello! Please enter your **Full Name** to begin."
    })

# ----------------------------
# FUNCTIONS
# ----------------------------
def get_next_order_number():
    file = "order_number.txt"

    if not os.path.exists(file):
        with open(file, "w") as f:
            f.write("1000")
        return 1000

    with open(file, "r") as f:
        num = int(f.read().strip())

    num += 1

    with open(file, "w") as f:
        f.write(str(num))

    return num


def log_to_csv(data):
    file = "acme_leads.csv"
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df = pd.DataFrame([data])

    if not os.path.exists(file):
        df.to_csv(file, index=False)
    else:
        df.to_csv(file, mode="a", header=False, index=False)


def format_work_order(data):
    return f"""
========================================
        ACME PLUMBING WORK ORDER
========================================
ORDER #: {data['order_number']}
DATE: {datetime.now().strftime('%Y-%m-%d')}
----------------------------------------
NAME: {data['name']}
PHONE: {data['phone']}
EMAIL: {data['email']}

ADDRESS:
{data['address']}

ISSUE:
{data['issue']}
----------------------------------------
SAFETY ADVICE:
{data['initial_advice']}
========================================
"""


def send_email(data, body):
    try:
        sender = os.getenv("MAIL_USERNAME")
        password = os.getenv("MAIL_PASSWORD")

        if not sender or not password:
            return "Missing email credentials"

        msg = MIMEText(body)
        msg["Subject"] = f"Work Order #{data['order_number']}"
        msg["From"] = sender
        msg["To"] = data["email"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        return True

    except Exception as e:
        return str(e)

# ----------------------------
# CHAT DISPLAY
# ----------------------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------
# CHAT INPUT FLOW
# ----------------------------
if prompt := st.chat_input("Enter details..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    reply = ""

    # NAME
    if st.session_state.step == "name":
        if len(prompt.split()) < 2:
            reply = "Please enter your full name."
        else:
            st.session_state.data["name"] = prompt
            st.session_state.step = "phone"
            reply = "What is your phone number?"

    # PHONE
    elif st.session_state.step == "phone":
        st.session_state.data["phone"] = prompt
        st.session_state.step = "email"
        reply = "What is your email address?"

    # EMAIL
    elif st.session_state.step == "email":
        if re.match(r'^[^@]+@[^@]+\.[^@]+$', prompt):
            st.session_state.data["email"] = prompt
            st.session_state.step = "address"
            reply = "What is your address?"
        else:
            reply = "Invalid email. Try again."

    # ADDRESS
    elif st.session_state.step == "address":
        st.session_state.data["address"] = prompt
        st.session_state.step = "issue"
        reply = "Describe the plumbing issue."

    # ISSUE + FINAL
    elif st.session_state.step == "issue":
        st.session_state.data["issue"] = prompt

        with st.spinner("Creating work order..."):
            order_no = get_next_order_number()
            st.session_state.data["order_number"] = order_no

            ai = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"Give 3 short safety tips for: {prompt}"
                }]
            )

            st.session_state.data["initial_advice"] = ai.choices[0].message.content

            log_to_csv(st.session_state.data.copy())

            work_order = format_work_order(st.session_state.data)
            st.session_state.work_order_text = work_order

            email_result = send_email(st.session_state.data, work_order)

            if email_result is True:
                reply = f"✅ Work order #{order_no} created and sent!"
            else:
                reply = f"Saved order #{order_no}, email failed: {email_result}"

        st.session_state.step = "complete"

    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    st.rerun()

# ----------------------------
# OUTPUT
# ----------------------------
if st.session_state.step == "complete":
    st.divider()
    st.text(st.session_state.work_order_text)

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    st.header("Admin")

    if st.button("Reset System"):
        st.session_state.clear()
        st.rerun()

    if os.path.exists("acme_leads.csv"):
        with open("acme_leads.csv", "rb") as f:
            st.download_button("Download Leads CSV", f, "acme_leads.csv")