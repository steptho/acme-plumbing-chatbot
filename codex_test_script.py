from openai import OpenAI

client = OpenAI(api_key="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")

response = client.responses.create(
    model="gpt-4.1-mini",
    input="Write a 5 line limerick about how awesome Jenson, a five year old boy who has just started school, is."
)

print(response.output_text)