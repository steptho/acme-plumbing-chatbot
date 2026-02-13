from openai import OpenAI
import os

# Clear the Screen
os.system("clear")
print("Cleared the screen")

# The SDK reads OPENAI_API_KEY from the environment by default.
client = OpenAI()

#  (api_key="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") 

response = client.chat.completions.create(
    model="o3",
    messages=[
        {
            "role": "user",
            "content": "Write a 5 line poem in the form of a limerick about how awesome Jenson a five year old boy that has just started school is.",
        }
    ],

)

print(response.choices[0].message.content)