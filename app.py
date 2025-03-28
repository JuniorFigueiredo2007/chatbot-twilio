from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os
from twilio.rest import Client as TwilioClient
import requests

app = Flask(__name__)

# Clientes
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"}
)

twilio_client = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

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

    content = [{"type": "text", "text": incoming_msg}]

    if num_media > 0:
        media_url = request.form.get('MediaUrl0')
        content_type = request.form.get('MediaContentType0')

        if 'image' in content_type:
            response = requests.get(media_url, auth=(
                os.getenv("TWILIO_ACCOUNT_SID"), 
                os.getenv("TWILIO_AUTH_TOKEN"))
            )

            # Upload direto para OpenAI
            image_upload = client.files.create(
                file=response.content,
                purpose="vision"
            )

            image_file_id = image_upload.id

            content.append({
                "type": "image_file",
                "image_file": {"file_id": image_file_id}
            })

    # Enviar mensagem com texto e imagem (se existir)
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content
    )

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
