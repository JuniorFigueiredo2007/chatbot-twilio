from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os
from twilio.rest import Client as TwilioClient
import requests

app = Flask(__name__)

# Cliente OpenAI com GPT-4 Vision habilitado
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), default_headers={"OpenAI-Beta": "assistants=v2"})

# Cliente Twilio
twilio_client = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

ASSISTANT_ID = "asst_mlwRF5Byw4b4gqlYz9jvJtwV"

ultima_interacao = {}
user_threads = {}

@app.route('/bot', methods=['POST'])
def whatsapp_reply():
    sender = request.form.get('From')
    incoming_msg = request.form.get('Body', '').strip()
    num_media = int(request.form.get('NumMedia', 0))

    if 'g.us' in sender:
        return ''

    agora = time.time()
    ultima_interacao[sender] = agora

    if sender not in user_threads:
        thread = client.beta.threads.create()
        user_threads[sender] = thread.id

    thread_id = user_threads[sender]

    if num_media > 0:
        media_url = request.form.get('MediaUrl0')
        content_type = request.form.get('MediaContentType0')

        if 'image' in content_type:
            incoming_msg = "O cliente enviou uma imagem, por favor analise e responda adequadamente."
            
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=[
                    {"type": "text", "text": incoming_msg},
                    {"type": "image_url", "image_url": {"url": media_url}}
                ]
            )
        else:
            incoming_msg = "O cliente enviou um arquivo que não consigo interpretar. Informe-o por favor."
            client.beta.threads.messages.create(thread_id=thread_id, role="user", content=incoming_msg)
    else:
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=incoming_msg)

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    while run.status != "completed":
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    messages = client.beta.threads.messages.list(thread_id=thread_id)

    if messages.data:
        resposta_ia = messages.data[0].content[0].text.value.strip()
    else:
        resposta_ia = "Desculpe, não consegui gerar uma resposta. Por favor, tente novamente."

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)