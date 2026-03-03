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

# --- 2. INITIALIZE SESSION STATE ---
if "data" not in st.session_state:
    st.session_state.data = {"name": None, "phone": None, "email": None, "address": None, "issue": None, "initial_advice": ""}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "step" not in st.session_state:
    st.session_state.step = "name"

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("Missing OpenAI API Key.")

def get_next_order_number():
    file_name = "order_number.txt"
    # If the file doesn't exist, start at 1000
    if not os.path.exists(file_name):
        with open(file_name, "w") as f:
            f.write("1000")
        return 1000
    
    # Read the current number
    with open(file_name, "r") as f:
        current_no = int(f.read().strip())
    
    # Increment and save back
    next_no = current_no + 1
    with open(file_name, "w") as f:
        f.write(str(next_no))
    
    return next_no
    
def log_to_excel(data):
    file_name = "acme_leads.xlsx"
    # Ensure the order number and timestamp are in the data
    # (The order number will be added to the data dictionary in Step 5)
    data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_lead = pd.DataFrame([data])
    
    if not os.path.isfile(file_name):
        new_lead.to_excel(file_name, index=False)
    else:
        existing_df = pd.read_excel(file_name)
        updated_df = pd.concat([existing_df, new_lead], ignore_index=True)
        updated_df.to_excel(file_name, index=False)

# --- 3. EMAIL FUNCTION ---
def send_work_order(data):
    # Use the number we already generated
    work_order_id = data.get('order_number', 'PENDING')
    current_date = datetime.now().strftime("%Y-%m-%d")
    # ... (rest of the email logic)
    
    advice = data.get('initial_advice', 'Locate your stopcock immediately.')

    email_body = f"""
==================================================
           ACME PLUMBING - OFFICIAL WORK ORDER
==================================================
WORK ORDER ID: {work_order_id}
DATE:          {current_date}
--------------------------------------------------
DISPATCH STATUS: 
Help is on the way! A qualified technician has 
been notified and will call you on {data['phone']} 
shortly to confirm their arrival time.
--------------------------------------------------
CUSTOMER DETAILS:
Name:    {data['name']}
Phone:   {data['phone']}
Email:   {data['email']}

SERVICE LOCATION:
{data['address']}

NATURE OF EMERGENCY:
{data['issue']}
--------------------------------------------------
DISPATCHER'S INITIAL ADVICE:
{advice}
--------------------------------------------------
ESTIMATED COSTS (Emergency Call-Out):
- Call-Out Fee (First Hour):  £95.00
- Additional Hourly Rate:      £65.00

*All prices are subject to VAT where applicable.*
--------------------------------------------------
IMPORTANT DISCLAIMER:
The figures provided above are estimates for the initial
emergency response. The final bill may vary based on
the complexity of the repair, time spent on-site, and
any specialized parts required.
--------------------------------------------------
IMPORTANT INSTRUCTIONS:
1. Locate your internal stopcock and turn it
   CLOCKWISE immediately to stop water flow.
2. Please keep your phone line clear for the 
   technician's call.
==================================================
"""
    try:
        sender = st.secrets["MAIL_USERNAME"]
        password = st.secrets["MAIL_PASSWORD"]
        msg = MIMEText(email_body)
        msg['Subject'] = f"URGENT: Work Order {work_order_id} - {data['name']}"
        msg['From'] = sender
        msg['To'] = data['email']
        msg['Cc'] = sender 

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        return True, work_order_id
    except Exception as e:
        return False, str(e)

# --- 4. DISPLAY CHAT ---
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 5. CHAT LOGIC ---
if prompt := st.chat_input("Enter details..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    
    reply = "" 
    
    # --- STEP 1: NAME (The Gatekeeper) ---
    # --- STEP 1: NAME ---
    if st.session_state.step == "name":
        user_input = prompt.strip().lower()
        
        # 1. Check for greetings or "garbage" input
        invalid_names = ["hi", "hello", "hey", "test", "yo", "plumber", "help"]
        
        if user_input in invalid_names or len(user_input) < 2:
            reply = "Hello! I'd love to get a plumber out to you. Could you please start by telling me your **Full Name**?"
            # IMPORTANT: Do NOT change st.session_state.step here
        else:
            # 2. If it looks like a real name, save it and MOVE to phone step
            st.session_state.data["name"] = prompt.strip()
            st.session_state.step = "phone" # NOW we move the step forward
            reply = f"Thank you, {prompt.strip()}. What is the best **Phone Number** for our plumber to reach you on?"

    elif st.session_state.step == "phone":
        st.session_state.data["phone"] = prompt
        reply = "And what is your **Email Address** for the work order?"
        st.session_state.step = "email"

    elif st.session_state.step == "email":
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', prompt):
            st.session_state.data["email"] = prompt
            reply = "Got it. What is the **Full Address** of the emergency?"
            st.session_state.step = "address"
        else:
            reply = "Please enter a valid email address."

    elif st.session_state.step == "address":
        st.session_state.data["address"] = prompt
        reply = "One last thing: **What is the plumbing emergency?**"
        st.session_state.step = "issue"

    elif st.session_state.step == "issue":
        st.session_state.data["issue"] = prompt
        with st.spinner("🚨 Finalizing work order & logging lead..."):
            # 1. Get the order number and AI advice
            order_no = get_next_order_number()
            st.session_state.data['order_number'] = order_no
            
            advice_res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Provide 3 short safety tips for this plumbing issue."}],
            )
            st.session_state.data['initial_advice'] = advice_res.choices[0].message.content
            
            # --- 2. ADD PRICING TO DATA FOR EXCEL ---
            st.session_state.data['call_out_fee'] = "£95.00"
            st.session_state.data['hourly_rate'] = "£65.00"
            st.session_state.data['disclaimer'] = "Estimate only. Final bill may vary based on complexity and parts."
            
            # 3. Log to Excel (Now including the prices)
            log_to_excel(st.session_state.data.copy())
            
            # 4. Send the email
            success, info = send_work_order(st.session_state.data)
            
            if success:
                reply = (f"### ✅ Dispatch Confirmed! (Work Order #{order_no})\n\n"
                        f"Help is on the way! A plumber will call you shortly.")
            else:
                reply = f"Details logged as Order #{order_no}, but email failed."
        
        st.session_state.step = "chatting"

    elif st.session_state.step == "chatting":
        with st.spinner("AI Dispatcher is thinking..."):
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a professional dispatcher for ACME Plumbing."}] + st.session_state.chat_history
            )
            reply = response.choices[0].message.content

    # SAVE AND RERUN (CRITICAL FIX)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    st.rerun()

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("Admin Tools")
    st.info(f"Status: {st.session_state.step.upper()}")
    if st.button("🗑️ Reset Dispatch Bot"):
        st.session_state.data = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        st.session_state.chat_history = []
        st.session_state.step = "name"
        st.rerun()
    