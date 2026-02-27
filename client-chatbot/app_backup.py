import os
import re
from flask import Flask, request, jsonify, render_template, session
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from services.openai_service import get_chat_response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "acme-plumbing-2026")

# --- Flask-Mail Setup ---
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_USERNAME")
)
mail = Mail(app)

limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day"], storage_uri="memory://")

# --- Prompts ---
COLLECTION_PROMPT = """You are the ACME Plumbing Dispatcher. 
CRITICAL RULE: You have NO power to dispatch a plumber yet. 
You MUST collect the user's Name, Phone, Email, and Address first. 
If the user says 'emergency', tell them: 'I can help, but I cannot dispatch anyone until I have your details.'
Do NOT say 'help is on the way' until the user provides their email and house address."""
SUPPORT_PROMPT = "You have all details. Reassure the customer that a technician is being dispatched. Do not ask for info again."

def get_next_work_order_number():
    file_path = "order_number.txt"
    try:
        if not os.path.exists(file_path):
            with open(file_path, "w") as f: f.write("1000")
        with open(file_path, "r") as f:
            current_num = int(f.read().strip())
        next_num = current_num + 1
        with open(file_path, "w") as f: f.write(str(next_num))
        return f"ACME-{next_num}"
    except: return "ACME-9999"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    user_input = request.json.get("message", "").strip()
    
    # 1. SESSION INITIALIZATION
    if "data" not in session:
        session["data"] = {"name": None, "phone": None, "email": None, "address": None}
    if "history" not in session or not session["history"]:
        session["history"] = [{"role": "system", "content": COLLECTION_PROMPT}]
        session["email_sent"] = False

    if user_input.lower() == "reset":
        session.clear()
        return jsonify({"response": "System reset. Please provide your Name to begin."})

    data = session["data"]

    # 2. HARVESTER (Updates data if found in message)
    email_match = re.search(r'[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+', user_input)
    if email_match: data["email"] = email_match.group(0)
    
    phone_match = re.search(r'(\d{10,15})', user_input.replace(" ", ""))
    if phone_match: data["phone"] = phone_match.group(0)

    if not data["name"] and len(user_input.split()) < 4 and not any(word in user_input.lower() for word in ["help", "emergency"]):
        data["name"] = user_input.title()

    if data["name"] and data["phone"] and data["email"] and not data["address"]:
        if len(user_input) > 10 and user_input.lower() not in [data["name"].lower(), data["email"].lower()]:
            data["address"] = user_input

    session["data"] = data
    print(f"DEBUG DATA STATE: {session['data']}")

    # 3. THE TRIGGER (Check EVERY turn, even if data was already there)
    # If all 4 fields are filled, and we haven't sent the email THIS session...
    if all(data.values()) and not session.get("email_sent"):
        print("--- !!! CRITICAL TRIGGER: SENDING WORK ORDER NOW !!! ---")
        if send_lead_email(data["email"], session["history"]):
            session["email_sent"] = True
            # Update personality to Support Mode
            session["history"][0] = {"role": "system", "content": SUPPORT_PROMPT}
            print("--- !!! SUCCESS: EMAIL DELIVERED !!! ---")

    # 4. CONVERSATION LOGIC
    # If we are STILL missing data, don't even ask the AI. Python handles the request.
    if not data["name"]:
        display_response = "I can help with your emergency, but first: What is your **Name**?"
    elif not data["phone"]:
        display_response = f"Thanks {data['name']}. What is your **Phone Number**?"
    elif not data["email"]:
        display_response = "Got it. And your **Email Address**?"
    elif not data["address"]:
        display_response = "Finally, what is the **Full Address** for the technician?"
    else:
        # If everything is sent, NOW let the AI talk
        session["history"].append({"role": "user", "content": user_input})
        display_response = get_chat_response(session["history"])

    # 5. UI & SAVE
    session["history"].append({"role": "assistant", "content": display_response})
    if any(word in user_input.lower() for word in ["emergency", "help", "flood"]):
        display_response += "\n\n⚠️ **EMERGENCY:** Please use the 'Call Now' button above to speak with our on-call plumber immediately!"

    session.modified = True
    return jsonify({"response": display_response})

def send_lead_email(customer_email, chat_history):
    try:
        work_order_id = get_next_work_order_number()
        
        # Pull the clean data from the session
        data = session.get("data", {})
        customer_name = data.get("name", "Not Provided")
        customer_phone = data.get("phone", "Not Provided")
        customer_address = data.get("address", "Not Provided")

        # --- THE INVOICE BODY ---
        msg = Message(
            subject=f"URGENT: Work Order {work_order_id} - {customer_name}",
            recipients=[customer_email]
        )
        msg.cc = [os.getenv("MAIL_USERNAME")]

        msg.body = f"""
==================================================
           ACME PLUMBING - OFFICIAL WORK ORDER
==================================================
WORK ORDER ID: {work_order_id}
DATE:          2026-02-26
--------------------------------------------------
CUSTOMER DETAILS:
Name:    {customer_name}
Phone:   {customer_phone}
Email:   {customer_email}

SERVICE LOCATION:
{customer_address}
--------------------------------------------------
IMPORTANT INSTRUCTIONS:
1. Locate your internal stopcock and turn it 
   CLOCKWISE immediately to stop water flow.
2. Clear the area around the leak to allow the 
   plumber quick access.
3. Our technician will confirm arrival via phone.

ESTIMATED COSTS (Emergency Call-Out):
- Call-Out Fee (First Hour):  £95.00
- Additional Hourly Rate:     £65.00
- Parts/Materials:           TBD by Technician

*All prices are subject to VAT where applicable.*
--------------------------------------------------
IMPORTANT DISCLAIMER:
The figures provided above are estimates for the initial 
emergency response. The final bill may vary based on 
the complexity of the repair, time spent on-site, and 
any specialized parts required. You will be asked to 
authorize any significant costs before work commences.
--------------------------------------------------
NEXT STEPS:
1. Turn off your main water valve (stopcock).
2. Clear a path for the technician.
3. Keep your phone line clear for our arrival call.

Thank you for choosing ACME Plumbing.
==================================================

Thank you for choosing ACME Plumbing.
==================================================
"""
        mail.send(msg)
        print(f">>> SUCCESS: Work Order {work_order_id} sent for {customer_name}")
        return True
    except Exception as e:
        print(f"--- MAIL ERROR: {str(e)} ---")
        return False

if __name__ == "__main__":
    app.run(debug=True, port=5001)