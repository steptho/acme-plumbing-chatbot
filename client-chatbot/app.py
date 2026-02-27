# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "acme-emergency-session-12345")

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

def send_lead_email(data):
    """Sends the professional formatted work order email."""
    try:
        work_order_id = datetime.now().strftime("%H%M%S")
        current_date = datetime.now().strftime("%Y-%m-%d")

        msg = Message(
            subject=f"URGENT: Work Order {work_order_id} - {data.get('name')}",
            recipients=[data.get('email')]
        )
        # Optional: CC yourself so you see the leads coming in
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
any specialized parts required.
==================================================
"""
        mail.send(msg)
        print(f"SUCCESS: Professional Work Order {work_order_id} sent.")
        return True
    except Exception as e:
        print(f"MAIL ERROR: {e}")
        return False

def get_chat_response(history):
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key: 
            return "I've logged your emergency. Please turn off your water main immediately while a plumber is dispatched."
        
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
    try:
        user_input = request.json.get("message", "").strip()
        
        if "data" not in session:
            session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        if "history" not in session:
            session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
            session["email_sent"] = False

        if user_input.lower() == "reset":
            session.clear()
            return jsonify({"response": "System reset. Welcome to ACME Plumbing. What is your **Name**?"})

        data = session["data"]
        history = session["history"]

        # Step-by-step data collection logic
        if not data["name"]:
            data["name"] = user_input
            reply = f"Hello {user_input}! What is a good **Phone Number** for the plumber to reach you?"
        elif not data["phone"]:
            data["phone"] = user_input
            reply = "And what is your **Email Address** for the work order?"
        elif not data["email"]:
            data["email"] = user_input
            reply = "Got it. What is the **Full Address** where the emergency is happening?"
        elif not data["address"]:
            data["address"] = user_input
            reply = "One last thing: **What is the plumbing emergency?** (e.g., burst pipe, leak)"
        elif not data["issue"]:
            data["issue"] = user_input
            # Now trigger the professional email
            if not session.get("email_sent"):
                send_lead_email(data)
                session["email_sent"] = True
            
            history.append({"role": "user", "content": user_input})
            reply = get_chat_response(history)
        else:
            history.append({"role": "user", "content": user_input})
            reply = get_chat_response(history)

        # Save back to session
        history.append({"role": "assistant", "content": reply})
        session["data"] = data
        session["history"] = history
        session.modified = True
        
        return jsonify({"response": reply})

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return jsonify({"response": "I'm having a quick technical hiccup. Could you please tell me your **Name** again?"})

if __name__ == '__main__':
    app.run(debug=True)