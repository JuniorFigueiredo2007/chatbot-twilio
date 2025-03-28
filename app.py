from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time
import os
from twilio.rest import Client as TwilioClient
import requests
from io import BytesIO
import fitz
from docx import Document
import openpyxl
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

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

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
gclient = gspread.authorize(creds)
sheet = gclient.open("Contatos WhatsApp Camila I.A").sheet1

def extrair_texto_pdf(conteudo):
    pdf_documento = fitz.open(stream=conteudo, filetype="pdf")
    texto = ""
    for pagina in pdf_documento:
        texto += pagina.get_text()
    return texto.strip()

def extrair_texto_word(conteudo):
    documento = Document(BytesIO(conteudo))
    return "\n".join([p.text for p in documento.paragraphs])

def extrair_texto_excel(conteudo):
    workbook = openpyxl.load_workbook(BytesIO(conteudo), data_only=True)
    sheet = workbook.active
    texto = ""
    for row in sheet.iter_rows(values_only=True):
        linha = [str(cell) for cell in row if cell is not None]
        texto += ' '.join(linha) + '\n'
    return texto.strip()

def processar_em_background(sender, incoming_msg, num_media, request_form):
    try:
        print("🔧 Iniciando processamento em background")
        print("📨 Mensagem recebida de:", sender)
        print("📎 Texto:", incoming_msg)
        print("📷 Número de mídias:", num_media)

        if 'g.us' in sender:
            print("⚠️ Mensagem de grupo ignorada.")
            return

        print("📝 Salvando contato no Google Sheets...")
        agora = time.time()
        ultima_interacao[sender] = agora

        if sender not in sheet.col_values(1):
            sheet.append_row([sender, datetime.now().strftime("%d/%m/%Y %H:%M:%S")])

        if sender not in user_threads:
            thread = client.beta.threads.create()
            user_threads[sender] = thread.id

        thread_id = user_threads[sender]

        if num_media > 0:
            print("📥 Baixando e processando mídia recebida...")
            media_url = request_form.get('MediaUrl0')
            content_type = request_form.get('MediaContentType0')

            response = requests.get(media_url, auth=(
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"))
            )
            conteudo = response.content

            if 'image' in content_type:
                content = [
                    {"type": "image_url", "image_url": {"url": media_url + ".jpg"}},
                    {"type": "text", "text": incoming_msg or "Descreva o conteúdo dessa imagem."}
                ]
            elif 'pdf' in content_type:
                texto = extrair_texto_pdf(conteudo)
                content = f"O cliente enviou um PDF com o seguinte texto: {texto}"
            elif 'word' in content_type:
                texto = extrair_texto_word(conteudo)
                content = f"O cliente enviou um documento Word com o seguinte texto: {texto}"
            elif 'sheet' in content_type:
                texto = extrair_texto_excel(conteudo)
                content = f"O cliente enviou uma planilha com o seguinte texto: {texto}"
            else:
                content = "Recebemos a mídia, mas não conseguimos processá-la."

            print("📤 Enviando mensagem com conteúdo para OpenAI...")
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=content
            )
        else:
            print("🗨️ Enviando mensagem de texto simples para OpenAI...")
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=incoming_msg
            )

        print("⏳ Aguardando resposta do Assistente...")
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)

        while run.status != "completed":
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        if messages.data:
            resposta_ia = messages.data[0].content[0].text.value.strip()
        else:
            resposta_ia = "Desculpe, não consegui gerar uma resposta."

        print("✅ Enviando resposta final ao WhatsApp...")
        twilio_client.messages.create(
            from_="whatsapp:" + os.getenv("TWILIO_PHONE_NUMBER"),
            to=sender,
            body=resposta_ia
        )

    except Exception as e:
        print("❌ Erro no processamento:", e)

@app.route('/bot', methods=['POST'])
def whatsapp_reply():
    print("📩 Requisição recebida no /bot — resposta imediata")

    sender = request.form.get('From')
    incoming_msg = request.form.get('Body', '').strip()
    num_media = int(request.form.get('NumMedia', 0))

    # CHAMADA DIRETA (sem thread)
    processar_em_background(sender, incoming_msg, num_media, request.form)

    resposta = MessagingResponse()
    resposta.message("Recebi sua imagem! Estou analisando e te respondo em instantes.")
    return Response(str(resposta), mimetype='text/xml')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
