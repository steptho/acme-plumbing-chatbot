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
    # Get the message from the website front-end
    user_input = request.json.get("message", "").strip()
    
    # 1. Initialize Session if it's a new conversation
    if "data" not in session:
        session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
    if "history" not in session:
        # COLLECTION_PROMPT should be defined at the top of your app.py
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False

    # 2. Handle Reset Command
    if user_input.lower() == "reset":
        session.clear()
        session["data"] = {"name": None, "phone": None, "email": None, "address": None, "issue": None}
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False
        return jsonify({"response": "System reset. Welcome to ACME Plumbing. What is your **Name** to begin?"})

    # 3. Add User Message to History (OpenAI Dictionary Format)
    session["history"].append({"role": "user", "content": user_input})

    # 4. Data Collection Logic (The "Form Filler")
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
        
        # --- ALL DATA COLLECTED: PROCESS LEAD ---
        print(f"--- !!! ALL DATA FOUND: PROCESSING LEAD FOR {data['name']} !!! ---")
        
        if not session.get("email_sent"):
            # This calls your function with the 'try/except' block
            send_lead_email(data["email"]) 
            session["email_sent"] = True
        
        # Now get the AI's response/advice for the emergency
        response_text = get_chat_response(session["history"])
    else:
        # If all data is already collected, just let the AI handle the chat
        response_text = get_chat_response(session["history"])

    # Update session data and save history
    session["data"] = data
    session["history"].append({"role": "assistant", "content": response_text})
    
    # CRITICAL: Tell Flask the session has changed so it saves to the cookie
    session.modified = True 
    
    return jsonify({"response": response_text})

if __name__ == '__main__':
    app.run(port=5001, debug=True)