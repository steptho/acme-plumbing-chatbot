# -*- coding: utf-8 -*-
import os
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

app = Flask(__name__)
# Fallback key ensures sessions work even if env var is missing
app.secret_key = os.getenv("FLASK_SECRET_KEY", "acme-emergency-session-123")

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
    return datetime.now().strftime("%H%M%S")

def send_lead_email(customer_email):
    """Sends the formal work order email with a safety net to prevent crashes."""
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
any specialized parts required.
==================================================
"""
        mail.send(msg)
        print(f"SUCCESS: Email sent for WO {work_order_id}")
        return True
    except Exception as e:
        print(f"MAIL ERROR (likely Render port block): {e}")
        return False

def get_chat_response(history):
    """Calls OpenAI safely. Falls back to text if API fails."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "I've logged your emergency. Please turn off your water main immediately."
        
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=history,
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "A plumber has been notified. Please ensure your stopcock is turned off while you wait."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json.get("message", "").strip()
        
        # 1. Initialize session variables
        if "data" not in session:
            session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        if "history" not in session:
            session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
            session["email_sent"] = False

        if user_input.lower() == "reset":
            session.clear()
            return jsonify({"response": "System reset. What is your **Name**?"})

        # 2. Add user input to local history copy
        current_history = session.get("history", [])
        current_history.append({"role": "user", "content": user_input})
        
        # 3. Pull data into local variable to edit
        data = session["data"]
        
        # 4. Sequential Data Collection Logic
        if not data.get("name"):
            data["name"] = user_input
            response_text = f"Hello {user_input}! What is a good **Phone Number** for the plumber to reach you?"
        elif not data.get("phone"):
            data["phone"] = user_input
            response_text = "And what is your **Email Address** for the work order?"
        elif not data.get("email"):
            data["email"] = user_input
            response_text = "Got it. What is the **Full Address** where the emergency is happening?"
        elif not data.get("address"):
            data["address"] = user_input
            response_text = "Final question: **What is the plumbing emergency?** (e.g., burst pipe, boiler leak)"
        elif not data.get("issue"):
            data["issue"] = user_input
            # Now that all data is collected, try to send the email
            if not session.get("email_sent"):
                send_lead_email(data["email"])
                session["email_sent"] = True
            response_text = get_chat_response(current_history)
        else:
            response_text = get_chat_response(current_history)

        # 5. Save everything back to session
        current_history.append({"role": "assistant", "content": response_text})
        session["history"] = current_history
        session["data"] = data
        session.modified = True 
        
        return jsonify({"response": response_text})

    except Exception as e:
        print(f"CRITICAL CHAT ERROR: {e}")
        return jsonify({"response": "Technical hiccup. Could you please try your last message again?"})

if __name__ == '__main__':
    app.run(debug=True)