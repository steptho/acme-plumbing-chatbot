# openai_template.py
import os
from openai import OpenAI

# 1️⃣ Set your API key in environment variable OPENAI_API_KEY
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_prompt(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 300):
    """
    Reusable function to send a prompt to OpenAI and get a response.
    
    :param prompt: The text prompt to send
    :param model: OpenAI model to use
    :param max_tokens: Max tokens for the response
    :return: Response text
    """
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

# 2️⃣ Examples
if __name__ == "__main__":
    poem = run_prompt("Write a short, funny poem about dogs.")
    print("📝 Poem:\n", poem)

    summary = run_prompt("Summarize the article: 'Captain Itoje back in England starting XV - reaction and Q&A'")
    print("\n📄 Summary:\n", summary)
