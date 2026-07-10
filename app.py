import os
import json
import logging
import subprocess
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime

# ========= CONFIGURAÇÕES =========
app = Flask(__name__)

# Carrega a chave da API de forma segura
API_KEY = os.getenv("LENIOR_API_KEY")
if not API_KEY:
    logging.warning("LENIOR_API_KEY não definida. Use variável de ambiente.")

# Escolha o provedor: 'openai', 'gemini', ou 'local'
PROVIDER = os.getenv("LENIOR_PROVIDER", "openai").lower()
API_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
    "local": "http://localhost:11434/api/generate"  # para Ollama
}
API_URL = API_URLS.get(PROVIDER, API_URLS["openai"])

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Memória simples (em produção use Redis)
historico = []

# ========= FUNÇÕES DA IA =========
def chamar_api(mensagens, temperatura=0.7, max_tokens=500):
    """Chama a API configurada com fallback."""
    try:
        if PROVIDER == "openai":
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": mensagens,
                "temperature": temperatura,
                "max_tokens": max_tokens
            }
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        
        elif PROVIDER == "gemini":
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": mensagens[-1]["content"]}]}]
            }
            params = {"key": API_KEY}
            resp = requests.post(API_URL, headers=headers, json=payload, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        elif PROVIDER == "local":
            # Para Ollama ou similar
            payload = {
                "model": "llama2",
                "prompt": mensagens[-1]["content"],
                "stream": False
            }
            resp = requests.post(API_URL, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["response"].strip()
        
        else:
            return "Provedor não suportado."
    
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        return f"Erro ao contactar IA: {str(e)}"

def conversar(pergunta):
    """Conversa normal com contexto."""
    mensagens = [
        {"role": "system", "content": "Você é o LENIOR, assistente pessoal inteligente, educado e prestativo. Responda em português brasileiro."},
        *historico[-5:],  # Últimas 5 trocas para contexto
        {"role": "user", "content": pergunta}
    ]
    resposta = chamar_api(mensagens)
    historico.append({"role": "user", "content": pergunta})
    historico.append({"role": "assistant", "content": resposta})
    return resposta

def gerar_codigo(descricao):
    """Gera código limpo e funcional."""
    prompt = f"Escreva apenas o código (sem explicações) para: {descricao}. Use a linguagem apropriada e inclua comentários se relevante."
    mensagens = [
        {"role": "system", "content": "Você é um especialista em programação. Gere código otimizado e bem comentado."},
        {"role": "user", "content": prompt}
    ]
    return chamar_api(mensagens, temperatura=0.3, max_tokens=1000)

def executar_comando(comando):
    """Executa comando no sistema com segurança."""
    try:
        # Lista de comandos proibidos (pode expandir)
        proibidos = ["rm -rf", "del /f", "format", "shutdown", "reboot"]
        for proibido in proibidos:
            if proibido in comando.lower():
                return "❌ Comando bloqueado por segurança."

        if os.name == 'nt':
            processo = subprocess.run(comando, shell=True, capture_output=True, text=True, check=False)
        else:
            processo = subprocess.run(['sh', '-c', comando], capture_output=True, text=True, check=False)
        
        if processo.returncode == 0:
            return processo.stdout.strip() or "✅ Comando executado com sucesso."
        else:
            return f"❌ Erro: {processo.stderr.strip()}"
    except Exception as e:
        logger.error(f"Erro ao executar comando: {e}")
        return f"❌ Falha ao executar: {e}"

def identificar_intencao(entrada):
    """Classifica a intenção do usuário usando IA."""
    prompt = f"""
Classifique a intenção da seguinte frase em uma destas categorias (responda apenas com a categoria):
- "conversar" (perguntas, bate-papo, opiniões)
- "codigo" (pedido para escrever código, programar)
- "comando" (ações no computador, abrir programas, executar)

Frase: "{entrada}"
Categoria:
"""
    mensagens = [
        {"role": "system", "content": "Você classifica intenções."},
        {"role": "user", "content": prompt}
    ]
    resposta = chamar_api(mensagens, temperatura=0.0, max_tokens=10)
    resposta = resposta.lower().strip()
    if "codigo" in resposta:
        return "codigo"
    elif "comando" in resposta:
        return "comando"
    else:
        return "conversar"

# ========= ROTAS =========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/lenior', methods=['POST'])
def lenior_api():
    data = request.json
    mensagem = data.get('mensagem', '').strip()
    if not mensagem:
        return jsonify({'erro': 'Mensagem vazia'}), 400

    # Log da requisição
    logger.info(f"Usuário: {mensagem}")

    intencao = identificar_intencao(mensagem)
    resposta = ""
    tipo = "texto"
    comando_confirmar = None

    if intencao == "codigo":
        tipo = "codigo"
        resposta = gerar_codigo(mensagem)
    elif intencao == "comando":
        tipo = "comando"
        comando_confirmar = mensagem
        resposta = f"⚠️ Deseja executar: '{mensagem}' ?"
    else:
        tipo = "texto"
        resposta = conversar(mensagem)

    return jsonify({
        'resposta': resposta,
        'tipo': tipo,
        'comando': comando_confirmar
    })

@app.route('/api/executar', methods=['POST'])
def executar():
    data = request.json
    comando = data.get('comando', '').strip()
    if not comando:
        return jsonify({'erro': 'Comando vazio'}), 400
    
    resultado = executar_comando(comando)
    return jsonify({'resultado': resultado})

@app.route('/api/historico', methods=['GET'])
def get_historico():
    """Retorna o histórico de conversas (opcional)."""
    return jsonify(historico)

# ========= INICIALIZAÇÃO =========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
