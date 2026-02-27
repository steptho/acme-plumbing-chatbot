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
app.secret_key = os.getenv("FLASK_SECRET_KEY", "acme-emergency-session-final-v3")

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
    """Background task to send the professional formatted work order."""
    with app_context:
        try:
            work_order_id = datetime.now().strftime("%H%M%S")
            current_date = datetime.now().strftime("%Y-%m-%d")

            msg = Message(
                subject=f"URGENT: Work Order {work_order_id} - {data.get('name')}",
                recipients=[data.get('email')]
            )
            msg.cc = [os.getenv("MAIL_USERNAME")]
            
            # THE PROFESSIONAL TOUCH - RESTORED
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
        if not api_key: return "Please turn off your water main immediately."
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=history, max_tokens=150)
        return response.choices[0].message.content
    except:
        return "I've logged your emergency. Please turn off your stopcock clockwise now."

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
            return jsonify({"response": "System reset. How can ACME Plumbing help you today?"})

        data = session["data"]

        # 1. NAME 
        if not data.get("name"):
            greetings = ["hi", "hello", "hey", "help", "emergency"]
            if any(word in user_input.lower() for word in greetings) or len(user_input) > 20:
                reply = "I'm sorry to hear you're having trouble! I can certainly get a plumber out. To start the work order, **what is your Name?**"
            else:
                data["name"] = user_input
                reply = f"Thank you, {user_input}. What is a good **Phone Number**?"

        # 2. PHONE
        elif not data.get("phone"):
            data["phone"] = user_input
            reply = "And what is your **Email Address** for the work order?"

        # 3. EMAIL (With Validation)
        elif not data.get("email"):
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if re.match(email_pattern, user_input):
                data["email"] = user_input
                reply = "Got it. What is the **Full Address** where the emergency is happening?"
            else:
                reply = "That doesn't look like a valid email. Please check the spelling?"

        # 4. ADDRESS
        elif not data.get("address"):
            data["address"] = user_input
            reply = "One last thing: **What is the plumbing emergency?**"

        # 5. ISSUE & BACKGROUND EMAIL
        elif not data.get("issue"):
            data["issue"] = user_input
            if not session.get("email_sent"):
                # Run the work order email in the background
                thread = threading.Thread(target=send_email_async, args=(app.app_context(), data.copy()))
                thread.start()
                session["email_sent"] = True
            
            history = session.get("history", [])
            reply = get_chat_response(history + [{"role": "user", "content": user_input}])
        
        else:
            history = session.get("history", [])
            reply = get_chat_response(history + [{"role": "user", "content": user_input}])

        # Update Session
        session["data"] = data
        new_history = session.get("history", [])
        new_history.append({"role": "user", "content": user_input})
        new_history.append({"role": "assistant", "content": reply})
        session["history"] = new_history
        session.modified = True
        return jsonify({"response": reply})

    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"response": "I'm still here! Could you please type that again?"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)