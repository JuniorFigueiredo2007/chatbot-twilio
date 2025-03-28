from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os
from twilio.rest import Client as TwilioClient
import requests
from io import BytesIO
import fitz  # PyMuPDF para PDFs
from docx import Document  # Para Word
import openpyxl  # Para Excel
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

# Configuração da API OpenAI
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={"OpenAI-Beta": "assistants=v2"}
)

# Configuração da API Twilio
twilio_client = TwilioClient(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# ID do Assistente OpenAI
ASSISTANT_ID = "asst_mlwRF5Byw4b4gqlYz9jvJtwV"

# Variáveis de controle
ultima_interacao = {}
user_threads = {}

# Conexão com Google Sheets
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
gclient = gspread.authorize(creds)
sheet = gclient.open("Contatos WhatsApp Camila I.A").sheet1

# Funções auxiliares para extrair texto
def extrair_texto_pdf(conteudo):
    pdf_documento = fitz.open(stream=conteudo, filetype="pdf")
    texto = ""
    for pagina in pdf_documento:
        texto += pagina.get_text()
    return texto.strip()

def extrair_texto_word(conteudo):
    documento = Document(BytesIO(conteudo))
    return "\n".join([paragrafo.text for paragrafo in documento.paragraphs])

def extrair_texto_excel(conteudo):
    workbook = openpyxl.load_workbook(BytesIO(conteudo), data_only=True)
    sheet = workbook.active
    texto = ""
    for row in sheet.iter_rows(values_only=True):
        linha = [str(cell) for cell in row if cell is not None]
        texto += ' '.join(linha) + '\n'
    return texto.strip()

@app.route('/bot', methods=['POST'])
def whatsapp_reply():
    print("📩 Requisição recebida no /bot")
    print("Form:", request.form)
    print("Headers:", request.headers)
    
    sender = request.form.get('From')
    incoming_msg = request.form.get('Body', '').strip()
    num_media = int(request.form.get('NumMedia', 0))

    if 'g.us' in sender:
        return ''

    agora = time.time()
    ultima_interacao[sender] = agora

    # Salva no Google Sheets se for novo
    contatos_existentes = sheet.col_values(1)
    if sender not in contatos_existentes:
        sheet.append_row([sender, datetime.now().strftime("%d/%m/%Y %H:%M:%S")])

    # Cria thread do usuário se não existir
    if sender not in user_threads:
        thread = client.beta.threads.create()
        user_threads[sender] = thread.id

    thread_id = user_threads[sender]

    # Se houver mídia anexada
    if num_media > 0:
        media_url = request.form.get('MediaUrl0')
        content_type = request.form.get('MediaContentType0')

        response = requests.get(media_url, auth=(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"))
        )
        conteudo = response.content

        if 'image' in content_type:
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": media_url + ".jpg"
                        }
                    },
                    {
                        "type": "text",
                        "text": incoming_msg or "Descreva o conteúdo dessa imagem, por favor."
                    }
                ]
            )
        elif 'pdf' in content_type:
            texto_extraido = extrair_texto_pdf(conteudo)
            incoming_msg = f"O cliente enviou um PDF com o seguinte texto: {texto_extraido}"
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=incoming_msg
            )
        elif 'msword' in content_type or 'wordprocessingml' in content_type:
            texto_extraido = extrair_texto_word(conteudo)
            incoming_msg = f"O cliente enviou um documento Word com o seguinte texto: {texto_extraido}"
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=incoming_msg
            )
        elif 'sheet' in content_type or 'spreadsheetml' in content_type:
            texto_extraido = extrair_texto_excel(conteudo)
            incoming_msg = f"O cliente enviou um Excel com o seguinte texto: {texto_extraido}"
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=incoming_msg
            )
    else:
        # Mensagem de texto normal
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=incoming_msg
        )

    # Executa a IA e espera a resposta
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

    # Envia a resposta para o WhatsApp
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
