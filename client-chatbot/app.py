# -*- coding: utf-8 -*-
import os
import re
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

app = Flask(__name__)
# Using a fallback for the secret key to ensure the session always works
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-plumbing-key")

# --- MAIL CONFIG ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")
mail = Mail(app)

# --- AI CONFIG ---
COLLECTION_PROMPT = "You are a helpful assistant for ACME Plumbing. Provide emergency advice once details are collected."

def get_next_work_order_number():
    # Placeholder for your actual work order logic
    return datetime.now().strftime("%H%M%S")

def send_lead_email(customer_email):
    try:
        work_order_id = get_next_work_order_number()
        current_date = datetime.now().strftime("%Y-%m-%d")
        data = session.get("data", {})

        msg = Message(
            subject=f"URGENT: Work Order {work_order_id} - {data.get('name')}",
            recipients=[customer_email]
        )
        msg.cc = [os.getenv("MAIL_USERNAME")]

        msg.body = f"""
==================================================
           ACME PLUMBING - OFFICIAL WORK ORDER
==================================================
WORK ORDER ID: {work_order_id}
DATE:          {current_date}
--------------------------------------------------
CUSTOMER DETAILS:
Name:    {data.get('name')}
Phone:   {data.get('phone')}
Email:   {data.get('email')}

SERVICE LOCATION:
{data.get('address')}

NATURE OF EMERGENCY:
{data.get('issue')}
--------------------------------------------------
IMPORTANT INSTRUCTIONS:
1. Locate your internal stopcock and turn it
   CLOCKWISE immediately to stop water flow.
2. Clear the area around the leak to allow the
   plumber quick access.
3. Our technician will confirm arrival via phone.
--------------------------------------------------
ESTIMATED COSTS (Emergency Call-Out):
- Call-Out Fee (First Hour):  £95.00
- Additional Hourly Rate:     £65.00

*All prices are subject to VAT where applicable.*
--------------------------------------------------
IMPORTANT DISCLAIMER:
The figures provided above are estimates for the initial
emergency response. The final bill may vary based on
the complexity of the repair, time spent on-site, and
any specialized parts required. You will be asked to
authorize any significant costs before work commences.
==================================================
"""
        mail.send(msg)
        print(f"SUCCESS: Work Order {work_order_id} sent.")
        return True
    except Exception as e:
        print(f"MAIL ERROR: {e}")
        return False

def get_chat_response(history):
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "I've received your details. Please ensure your water is turned off while we process your request."
        
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=history,
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "I've received your details and a plumber is being notified. Please turn off your water main immediately."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message", "").strip()
    
    if "data" not in session:
        session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
    if "history" not in session:
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False

    if user_input.lower() == "reset":
        session.clear()
        return jsonify({"response": "System reset. Welcome to ACME Plumbing. What is your **Name**?"})

    session["history"].append({"role": "user", "content": user_input})
    data = session["data"]
    
    if not data["name"]:
        data["name"] = user_input
        response_text = "Thanks! What is a good **Phone Number** for the plumber to reach you?"
    elif not data["phone"]:
        data["phone"] = user_input
        response_text = "And what is your **Email Address** for the work order?"
    elif not data["email"]:
        data["email"] = user_input
        response_text = "Got it. What is the **Full Address** where the emergency is happening?"
    elif not data["address"]:
        data["address"] = user_input
        response_text = "One last thing: **What is the plumbing emergency?** (e.g., burst pipe, leak)"
    elif not data["issue"]:
        data["issue"] = user_input
        if not session.get("email_sent"):
            send_lead_email(data["email"])
            session["email_sent"] = True
        response_text = get_chat_response(session["history"])
    else:
        response_text = get_chat_response(session["history"])

    session["data"] = data
    session["history"].append({"role": "assistant", "content": response_text})
    session.modified = True 
    
    return jsonify({"response": response_text})

if __name__ == '__main__':
    app.run(debug=True)