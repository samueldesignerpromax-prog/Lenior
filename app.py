import os
import subprocess
import requests
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ========= CONFIGURAÇÕES DA API =========
# Use variável de ambiente para a chave (seguro)
API_KEY = os.getenv("LENIOR_API_KEY", "")
if not API_KEY:
    print("⚠️  ATENÇÃO: LENIOR_API_KEY não definida. A IA não funcionará.")

# Altere a URL se estiver usando outro provedor
API_URL = os.getenv("API_URL", "https://api.openai.com/v1/chat/completions")

# ========= FUNÇÕES DA IA =========
def chamar_api(mensagens, temperatura=0.7, max_tokens=500):
    if not API_KEY:
        return "Erro: Chave de API não configurada."

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",  # Ou o modelo disponível
        "messages": mensagens,
        "temperature": temperatura,
        "max_tokens": max_tokens
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.Timeout:
        return "Erro: Tempo limite excedido ao chamar a API."
    except requests.exceptions.RequestException as e:
        return f"Erro na requisição: {e}"
    except (KeyError, json.JSONDecodeError) as e:
        return f"Erro ao processar resposta da API: {e}"

def conversar(pergunta):
    mensagens = [
        {"role": "system", "content": "Você é o LENIOR, um assistente pessoal inteligente, prestativo e educado. Responda em português."},
        {"role": "user", "content": pergunta}
    ]
    return chamar_api(mensagens)

def gerar_codigo(descricao):
    prompt = f"Escreva apenas o código (sem explicações extras) para: {descricao}. Use a linguagem apropriada."
    mensagens = [
        {"role": "system", "content": "Você é um especialista em programação. Gere código limpo e funcional."},
        {"role": "user", "content": prompt}
    ]
    return chamar_api(mensagens, temperatura=0.3, max_tokens=1000)

def executar_comando(comando):
    """
    Executa um comando no sistema operacional.
    Atenção: só execute comandos confiáveis!
    """
    try:
        # Limita comandos para maior segurança (opcional)
        comandos_permitidos = ["notepad", "calc", "explorer", "echo", "dir", "ls", "whoami"]
        # Se o comando não começar com um permitido, pode recusar
        # Vamos apenas executar com shell
        if os.name == 'nt':
            processo = subprocess.run(comando, shell=True, capture_output=True, text=True, check=False)
        else:
            processo = subprocess.run(['sh', '-c', comando], capture_output=True, text=True, check=False)
        if processo.returncode == 0:
            return processo.stdout.strip() or "Comando executado com sucesso."
        else:
            return f"Erro (código {processo.returncode}): {processo.stderr.strip()}"
    except Exception as e:
        return f"Falha ao executar: {e}"

def identificar_intencao(entrada):
    """
    Usa a IA para classificar a intenção do usuário.
    """
    prompt = f"""
Classifique a intenção da seguinte frase do usuário em uma destas categorias:
- "conversar" (perguntas gerais, bate-papo)
- "codigo" (pedidos para escrever código, programar)
- "comando" (ações no computador, abrir programas, executar algo)

Frase: "{entrada}"
Resposta apenas com a categoria (exatamente uma palavra):
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
    data = request.get_json()
    if not data or 'mensagem' not in data:
        return jsonify({'erro': 'Mensagem não fornecida'}), 400

    mensagem_usuario = data['mensagem'].strip()
    if not mensagem_usuario:
        return jsonify({'erro': 'Mensagem vazia'}), 400

    # 1. Classifica intenção
    intencao = identificar_intencao(mensagem_usuario)
    resposta = ""
    tipo_resposta = "texto"
    comando_confirmar = None

    try:
        if intencao == "codigo":
            tipo_resposta = "codigo"
            resposta = gerar_codigo(mensagem_usuario)
        elif intencao == "comando":
            tipo_resposta = "comando"
            comando_confirmar = mensagem_usuario
            resposta = f"Quer executar o comando: '{mensagem_usuario}' ?"
        else:
            tipo_resposta = "texto"
            resposta = conversar(mensagem_usuario)
    except Exception as e:
        return jsonify({'erro': f'Erro interno: {e}'}), 500

    return jsonify({
        'resposta': resposta,
        'tipo': tipo_resposta,
        'comando': comando_confirmar
    })

@app.route('/api/executar', methods=['POST'])
def executar():
    data = request.get_json()
    if not data or 'comando' not in data:
        return jsonify({'erro': 'Comando não fornecido'}), 400

    comando = data['comando'].strip()
    if not comando:
        return jsonify({'erro': 'Comando vazio'}), 400

    # Executa e retorna o resultado
    resultado = executar_comando(comando)
    return jsonify({'resultado': resultado})

# ========= INÍCIO DA APLICAÇÃO =========
if __name__ == '__main__':
    # A porta é fornecida pelo Render via variável de ambiente PORT
    port = int(os.environ.get('PORT', 5000))
    # Em produção, debug deve ser False
    app.run(host='0.0.0.0', port=port, debug=False)
