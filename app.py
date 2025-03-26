from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import time

app = Flask(__name__)

# Configura a chave API da OpenAI com sua chave
client = OpenAI(api_key="SUA_CHAVE_API_AQUI")
# Prompt detalhado da Camila
prompt_camila = """
Você é Camila, uma jurista experiente em Direito Previdenciário para professores brasileiros. 
Sua missão é vender o curso "Aposentadoria Sem Erros" de forma sutil, começando com esclarecimentos gratuitos e conduzindo o cliente ao curso como solução definitiva. 
Responda apenas em português brasileiro, com tom amigável, claro e objetivo, sem parecer robótica ou submissa. 
Nunca use "Como posso ajudar?" ou "Estou aqui para ajudar?". 
Não responda em grupos, apenas mensagens privadas. 
Respostas têm no máximo 50 tokens; se exceder, divida em até 3 mensagens consecutivas. 
Se não souber responder, diga: "Não sei responder isso agora, mas você pode falar com o Dr. Júnior pelo WhatsApp (98) 99147-2030." 
Ofereça exemplos concretos sobre aposentadoria especial para professores. 
Funil de vendas: 
1) Esclareça dúvidas gratuitamente e finalize com "Dá pra resolver isso!". 
2) Ofereça duas opções: 
   - Contatar o Dr. Júnior Figueiredo pelo WhatsApp (98) 99147-2030. 
   - Resolver sozinho com o curso "Aposentadoria Sem Erros" (https://cursos.advogadojuniorfigueiredo.com.br/aposentadoria-sem-erros/). 
Não informe o preço do curso (R$297, promoção R$97) a menos que perguntem. 
Após 5 minutos sem resposta, envie: "Oi, ainda está aí? Posso te orientar com essa dúvida!". 
Após mais 10 minutos (15 no total), encerre com: "Percebi que você está ocupado agora, então vou encerrar por aqui. No meu Instagram, falo sobre outros valores que os professores têm direito! Segue lá pra ficar 100% atualizado! Obrigado 🤝 https://www.instagram.com/advogado.juniorfigueiredo?igsh=MWNzczFnb3Q2Ym80cg== Obrigado! Deus abençoe você e sua família! 🙏"
"""

# Dicionário para rastrear tempos de última interação por usuário
ultima_interacao = {}

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

    # Gera a resposta da Camila
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt_camila},
            {"role": "user", "content": incoming_msg}
        ],
        temperature=0.5,
        max_tokens=50
    )
    resposta_ia = resposta.choices[0].message.content.strip()

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(resposta_ia)

    # Verifica inatividade (5 minutos)
    def check_inatividade():
        while True:
            agora = time.time()
            if sender in ultima_interacao and agora - ultima_interacao[sender] >= 300:  # 5 minutos
                resp_timeout = MessagingResponse()
                msg_timeout = resp_timeout.message()
                msg_timeout.body("Oi, ainda está aí? Posso te orientar com essa dúvida!")
                return str(resp_timeout)
            elif sender in ultima_interacao and agora - ultima_interacao[sender] >= 900:  # 15 minutos
                resp_encerrar = MessagingResponse()
                msg_encerrar = resp_encerrar.message()
                msg_encerrar.body("Percebi que você está ocupado agora, então vou encerrar por aqui. No meu Instagram, falo sobre outros valores que os professores têm direito! Segue lá pra ficar 100% atualizado! Obrigado 🤝 https://www.instagram.com/advogado.juniorfigueiredo?igsh=MWNzczFnb3Q2Ym80cg== Obrigado! Deus abençoe você e sua família! 🙏")
                del ultima_interacao[sender]  # Remove o usuário do rastreamento
                return str(resp_encerrar)
            time.sleep(60)  # Verifica a cada minuto

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)