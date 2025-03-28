from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os
import requests
from twilio.rest import Client as TwilioClient

app = Flask(__name__)

# Configuração correta com suporte a Assistants API v2
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"}
)

# Cliente Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

ASSISTANT_ID = "asst_mlwRF5Byw4b4gqlYz9jvJtwV"

ultima_interacao = {}
user_threads = {}

@app.route('/bot', methods=['POST'])
def whatsapp_reply():
    sender = request.form.get('From')
    incoming_msg = request.form.get('Body', '').strip()

    # Ignora grupos
    if 'g.us' in sender:
        return ''

    agora = time.time()
    ultima_interacao[sender] = agora

    if sender not in user_threads:
        thread = client.beta.threads.create()
        user_threads[sender] = thread.id

    thread_id = user_threads[sender]

    # Verifica se a mensagem tem mídia (áudio) e faz transcrição
    if int(request.form.get('NumMedia', 0)) > 0:
        media_url = request.form.get('MediaUrl0')
        media_content_type = request.form.get('MediaContentType0')

        if 'audio' in media_content_type:
            audio_file = requests.get(media_url)
            audio_filename = f'/tmp/{sender.replace("+", "")}.ogg'
            with open(audio_filename, 'wb') as f:
                f.write(audio_file.content)

            with open(audio_filename, 'rb') as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            incoming_msg = transcription.text

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=incoming_msg
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

    # Simulando que a Camila está digitando por alguns segundos antes de responder
    tempo_digitando = min(len(resposta_ia) * 0.05, 5)  # máximo 5 segundos
    time.sleep(tempo_digitando)

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
