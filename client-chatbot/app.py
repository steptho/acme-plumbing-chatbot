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
import csv


load_dotenv()

app = Flask(__name__)
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
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- LIMITER ---
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])

# --- PROMPTS ---
COLLECTION_PROMPT = "You are a helpful plumbing assistant. Be brief. Your goal is to collect Name, Phone, Email, Address, and the Nature of the Emergency."
SUPPORT_PROMPT = "The work order has been sent. You are now a supportive assistant. Advise the user to stay safe and turn off their water."

# --- HELPERS ---
def get_next_work_order_number():
    # This creates a unique ID based on the Month, Day, Hour, and Minute
    # Example: ACME-0226-1645
    return f"ACME-{datetime.now().strftime('%m%d-%H%M')}"

import csv

def log_lead_to_csv(data):
    file_path = 'acme_leads.csv'
    # The columns we want in our spreadsheet
    headers = ['Date', 'Name', 'Phone', 'Email', 'Address', 'Issue']
    
    # Check if the file exists to decide if we need to write the header
    file_exists = os.path.isfile(file_path)
    
    try:
        with open(file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            
            # Write the header only once at the top of the file
            if not file_exists:
                writer.writeheader()
            
            # Add the data row
            writer.writerow({
                'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Name': data.get('name'),
                'Phone': data.get('phone'),
                'Email': data.get('email'),
                'Address': data.get('address'),
                'Issue': data.get('issue')
            })
        print(">>> SUCCESS: Lead logged to acme_leads.csv")
        return True
    except Exception as e:
        print(f"CSV LOG ERROR: {e}")
        return False

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
        # This is where Render usually blocks the connection
        mail.send(msg)
        print(f"SUCCESS: Work Order {work_order_id} sent.")
        return True

    except Exception as e:
        # This prevents the "Error connecting to server" crash
        print(f"MAIL ERROR for Work Order {work_order_id}: {e}")
        # Returning False allows the bot to skip the email and finish the chat
        return False

def get_chat_response(history):
    try:
        # OpenAI uses the 'messages' list directly, we don't need 'start_chat'
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=history[-10:], # Send the last 10 messages for context
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "I've received your details and a plumber is being notified. Please ensure your main water valve is turned off while you wait."
# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get("message", "").strip()
    
    # 1. Initialize Session
    if "data" not in session:
        session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
    if "history" not in session:
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False

    if user_input.lower() == "reset":
        session.clear()
        session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False
        return jsonify({"response": "System reset. Welcome to ACME Plumbing. What is your **Name**?"})
    
    data = session["data"]
    # Default response to prevent UnboundLocalError
    display_response = "I'm sorry, I didn't quite catch that. Could you repeat it?"

    # 2. Harvester Logic
    emergency_keywords = ["help", "emergency", "leak", "problem", "burst", "water", "boiler", "repair", "reset", "clear"]
    
    # Only capture name if it's NOT an emergency keyword and NOT too long
    # 2. Harvester Logic
    # Add greetings to this list so they don't get captured as names
    ignore_keywords = [
        "help", "emergency", "leak", "problem", "burst", "water", "boiler", "repair", 
        "reset", "clear", "hi", "hello", "hey", "good morning", "good afternoon", "typing"
    ]
    
    # --- NAME ---
    if not data["name"]:
        # Check if the input contains any "ignore" words
        is_ignored = any(word in user_input.lower() for word in ignore_keywords)
        
        # Only capture if it's 1-3 words AND doesn't contain a greeting/emergency word
        if len(user_input.split()) < 4 and not is_ignored:
            data["name"] = user_input.title()
    
    # --- EMAIL ---
    email_match = re.search(r'[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+', user_input)
    if email_match: data["email"] = email_match.group(0)
    
    # --- PHONE ---
    phone_match = re.search(r'(\d{10,15})', user_input.replace(" ", ""))
    if phone_match: data["phone"] = phone_match.group(0)

    # --- ADDRESS --- (Only if we have Name/Phone/Email but no Address)
    if data["name"] and data["phone"] and data["email"] and not data["address"]:
        if len(user_input) > 8 and not email_match and not phone_match:
            data["address"] = user_input

    # --- ISSUE --- (Only if we have Address but no Issue)
    elif data["address"] and not data["issue"]:
        # If the user sends a new message after the address, it MUST be the issue
        if user_input.strip().lower() != data["address"].lower():
            data["issue"] = user_input

    session["data"] = data
    # IMPORTANT: Watch your terminal for this print!
    print(f"DEBUG DATA STATE: {session['data']}")

    # 3. Trigger Email & Logging
    if all(session["data"].values()) and not session.get("email_sent"):
        print("--- !!! ALL DATA FOUND: PROCESSING LEAD !!! ---")
        
        # Send the Email
        email_success = send_lead_email(session["data"]["email"])
        
        # Save to Excel/CSV
        log_success = log_lead_to_csv(session["data"])
        
        if email_success:
            session["email_sent"] = True
            session["history"][0] = {"role": "system", "content": SUPPORT_PROMPT}
    
    # 4. Conversation Flow Logic
    if not data["name"]:
        display_response = "Welcome to ACME Plumbing. What is your **Name** to begin?"
    elif not data["phone"]:
        display_response = f"Thanks {data['name']}. What is a good **Phone Number** for the plumber to reach you?"
    elif not data["email"]:
        display_response = "And what is your **Email Address** for the work order?"
    elif not data["address"]:
        display_response = "Got it. What is the **Full Address** where the emergency is happening?"
    elif not data["issue"]:
        display_response = "One last thing: **What is the plumbing emergency?** (e.g., burst pipe, leak)"
    else:
        # If everything is captured, let the AI handle the supportive chat
        session["history"].append({"role": "user", "content": user_input})
        display_response = get_chat_response(session["history"])

    # 5. Final UI Polish & Save
    if any(word in user_input.lower() for word in ["emergency", "help", "flood"]):
        display_response += "\n\n🚨 **Call 0800-ACME-NOW for immediate dispatch.**"

    session["history"].append({"role": "assistant", "content": display_response})
    session.modified = True
    return jsonify({"response": display_response})

if __name__ == '__main__':
    app.run(port=5001, debug=True)