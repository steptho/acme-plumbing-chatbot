from openai import OpenAI
import os

# Create client using your environment variable
client = OpenAI()

# Store conversation history
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."}
]

print("Chatbot started! Type 'quit' to exit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "quit":
        print("Goodbye!")
        break

    # Add user message to history
    messages.append({"role": "user", "content": user_input})

    # Send conversation to OpenAI
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages
    )

    assistant_reply = response.choices[0].message.content

    # Add assistant reply to history
    messages.append({"role": "assistant", "content": assistant_reply})

    print("\nAssistant:", assistant_reply, "\n")
