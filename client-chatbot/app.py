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
            return jsonify({"response": "System reset. How can ACME Plumbing help you today?"})

        data = session["data"]

        # --- STEP 1: ESTABLISH CONTACT & GET NAME ---
        if not data.get("name"):
            # If they haven't given a name yet, check if their message is just a greeting or a problem
            greetings = ["hi", "hello", "hey", "help", "emergency", "plumber"]
            
            # If they just said "Hi" or described a problem without a name
            if any(word in user_input.lower() for word in greetings) or len(user_input) > 15:
                reply = "I'm sorry to hear you're having trouble! I can certainly get a plumber out to you. To start the work order, **what is your Name?**"
            else:
                # If they actually typed a name-like string
                data["name"] = user_input
                reply = f"Thank you, {user_input}. What is a good **Phone Number** for the plumber to reach you?"
        
        # --- STEP 2: PHONE (With simple length check) ---
        elif not data.get("phone"):
            # Basic check: Is it mostly digits and at least 10 characters?
            clean_phone = ''.join(filter(str.isdigit, user_input))
            if len(clean_phone) >= 10:
                data["phone"] = user_input
                reply = "Got it. And what is your **Email Address** so I can send over the work order?"
            else:
                reply = "I'll need a valid **Phone Number** so the plumber can call you when they are outside. What's the best number?"
       
        # --- STEP 3: EMAIL (With Validation) ---
        elif not data.get("email"):
            # A simple regex pattern for email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            
            if re.match(email_pattern, user_input):
                data["email"] = user_input
                reply = "Perfect. What is the **Full Address** where the emergency is happening?"
            else:
                reply = "That doesn't look quite right. Could you please double-check your **Email Address**? (e.g., name@email.com)"
        
        # --- STEP 4: ADDRESS ---
        elif not data.get("address"):
            data["address"] = user_input
            reply = "One last thing: **What is the plumbing emergency?** (e.g., burst pipe, leak, no hot water)"

        # --- STEP 5: ISSUE & SEND ---
        elif not data.get("issue"):
            data["issue"] = user_input
            
            if not session.get("email_sent"):
                # Use the background thread we set up earlier to prevent timeouts!
                thread = threading.Thread(target=send_email_async, args=(app.app_context(), data.copy()))
                thread.start()
                session["email_sent"] = True
            
            reply = get_chat_response(session["history"] + [{"role": "user", "content": user_input}])
        
        # --- STEP 6: CHAT ---
        else:
            reply = get_chat_response(session["history"] + [{"role": "user", "content": user_input}])

        # Save session
        session["data"] = data
        new_history = session.get("history", [])
        new_history.append({"role": "user", "content": user_input})
        new_history.append({"role": "assistant", "content": reply})
        session["history"] = new_history
        session.modified = True 
        
        return jsonify({"response": reply})

    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"response": "I'm still here! Please tell me your **Name** so I can continue."})
if __name__ == '__main__':
    app.run(debug=True)