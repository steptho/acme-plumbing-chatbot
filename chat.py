from openai import OpenAI
import os
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
# print(response)


# ChatCompletion(
#     id='chatcmpl-D7kY9PXmP89cDTI17o0XzZlPdmDxW',
#      choices=[
#      Choice(
#         finish_reason='stop', index=0, logprobs=None, 
#         message=ChatCompletionMessage(
#             content='There once was a bright lad named Jenson,  \nAt five, he outshines every lesson.  \nWith a grin ear-to-ear,  \nHe spreads joy far and near,  \nTurning school into pure fun-filled heaven!', 
#             refusal=None, 
#             role='assistant', 
#             annotations=[], 
#             audio=None, 
#             function_call=None, 
#             tool_calls=None))],
#      created=1770739605, 
#      model='o3-2025-04-16', 
#      object='chat.completion', 
#      service_tier='default', 
#      system_fingerprint=None, 
#      usage=CompletionUsage(completion_tokens=67, 
#      prompt_tokens=37, 
#      total_tokens=104, 
#      completion_tokens_details=CompletionTokensDetails(
#      accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0)))
# (venv311)






