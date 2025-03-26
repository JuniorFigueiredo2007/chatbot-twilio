from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os

app = Flask(__name__)

# Configura o cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ID do Assistente (Camila)
ASSISTANT_ID = "asst_mlwRF5BYw4b4gyl2jVtlwV"

# Dicionário para rastrear tempos de última interação e threads por usuário
ultima_interacao = {}
user_threads = {}

@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.form.get('From')  # Identificador do remetente
    incoming_msg = request.form.get('Body', '').strip()  # Mensagem recebida

    # Bloqueia respostas em grupos
    if 'g.us' in sender:
        return ''

    # Atualiza o tempo da última interação
    agora = time.time()
    ultima_interacao[sender] = agora

    # Verifica se o usuário já tem uma thread; se não, cria uma nova
    if sender not in user_threads:
        thread = client.beta.threads.create()
        user_threads[sender] = thread.id
    thread_id = user_threads[sender]

    # Adiciona a mensagem do usuário à thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=incoming_msg
    )

    # Executa o assistente na thread
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    # Aguarda a resposta do assistente
    while run.status != "completed":
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    # Obtém a resposta mais recente
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    resposta_ia = messages.data[0].content[0].text.value.strip()

    # Envia a resposta ao usuário
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)