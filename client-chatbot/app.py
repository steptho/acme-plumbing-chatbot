# -*- coding: utf-8 -*-
import os
import re
import threading
from flask import Flask, render_template, request, jsonify, session
from flask_mail import Mail, Message
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

app = Flask(__name__)
# Safety fallback for the secret key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "acme-emergency-session-final-v5")

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

def send_email_async(app_context, data):
    with app_context:
        try:
            work_order_id = datetime.now().strftime("%H%M%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            msg = Message(
                subject=f"URGENT: Work Order {work_order_id} - {data.get('name')}",
                recipients=[data.get('email')]
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
            print(f"BACKGROUND SUCCESS: Work Order {work_order_id} sent.")
        except Exception as e:
            print(f"BACKGROUND MAIL ERROR: {e}")

def get_chat_response(history):
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key: return None
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=history, max_tokens=150)
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {e}")
        return None

@app.route('/')
def index():
    # This renders the index.html from the /templates folder
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json.get("message", "").strip()
        
        # Initialize session keys if missing
        if "data" not in session:
            session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        if "history" not in session:
            session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
            session["email_sent"] = False

        if user_input.lower() == "reset":
            session.clear()
            return jsonify({"response": "System reset. How can ACME Plumbing help?"})

        data = session["data"]
        
        # Logic Loop
        if not data.get("name"):
            greetings = ["hi", "hello", "hey", "help", "emergency"]
            if any(word in user_input.lower() for word in greetings) or len(user_input) > 20:
                reply = "I'm sorry to hear that! I can help. To start, what is your **Name**?"
            else:
                data["name"] = user_input
                reply = f"Thank you, {user_input}. What is a good **Phone Number**?"
        elif not data.get("phone"):
            data["phone"] = user_input
            reply = "And what is your **Email Address**?"
        elif not data.get("email"):
            if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', user_input):
                data["email"] = user_input
                reply = "Got it. What is the **Full Address** of the emergency?"
            else:
                reply = "Please enter a valid email address so I can send the work order."
        elif not data.get("address"):
            data["address"] = user_input
            reply = "One last thing: **What is the plumbing emergency?**"
        elif not data.get("issue"):
            data["issue"] = user_input
            if not session.get("email_sent"):
                thread = threading.Thread(target=send_email_async, args=(app.app_context(), data.copy()))
                thread.start()
                session["email_sent"] = True
            
            ai_reply = get_chat_response(session["history"] + [{"role": "user", "content": user_input}])
            reply = ai_reply if ai_reply else "Details logged. Please turn off your stopcock clockwise now."
        else:
            ai_reply = get_chat_response(session["history"] + [{"role": "user", "content": user_input}])
            reply = ai_reply if ai_reply else "I've alerted the team. Please stay safe."

        # Save session
        session["data"] = data
        hist = session.get("history", [])
        hist.append({"role": "user", "content": user_input})
        hist.append({"role": "assistant", "content": reply})
        session["history"] = hist
        session.modified = True
        
        return jsonify({"response": reply})

    except Exception as e:
        print(f"CRITICAL CHAT ERROR: {e}")
        return jsonify({"response": "I'm having a connection issue. Can you please tell me your **Name** again?"})

if __name__ == '__main__':
    # For local testing
    app.run(debug=True)