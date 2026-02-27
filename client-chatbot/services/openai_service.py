import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_chat_response(messages):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages, 
            temperature=0,  # 0 makes the bot follow instructions strictly
            max_tokens=300  # Added to ensure complete but concise responses
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI: {e}")
        return "I'm sorry, I'm having a bit of trouble connecting to my dispatch system. Please try again in a moment."