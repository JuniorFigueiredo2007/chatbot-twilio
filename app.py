from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import requests
import os
import time
from twilio.rest import Client as TwilioClient

app = Flask(__name__)

# Configuração do OpenAI Client com suporte à Assistants API v2
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
    num_media = int(request.form.get('NumMedia', 0))

    if 'g.us' in sender:
        return ''

    agora = time.time()
    ultima_interacao[sender] = agora

    # Transcrição do áudio (se houver)
    if num_media > 0:
        media_type = request.form.get('MediaContentType0')
        if 'audio' in media_type or 'ogg' in media_type:
            audio_url = request.form.get('MediaUrl0')
            audio_file = requests.get(audio_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))

            with open('/tmp/audio.mp3', 'wb') as f:
                f.write(audio_file.content)

            # Usando Whisper da OpenAI
            with open('/tmp/audio.mp3', 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format='text'
                )
                incoming_msg = transcript.strip()

    if sender not in user_threads:
        thread = client.beta.threads.create()
        user_threads[sender] = thread.id

    thread_id = user_threads[sender]

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

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    return str(resp)

@app.route('/sms', methods=['POST'])
def sms_forward():
    sender = request.form.get('From')
    message_body = request.form.get('Body', '').strip()

    twilio_client.messages.create(
        body=f"SMS de {sender}: {message_body}",
        from_=os.getenv("TWILIO_NUMBER"),
        to=os.getenv("FORWARD_TO_NUMBER")
    )

    resp = MessagingResponse()
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
