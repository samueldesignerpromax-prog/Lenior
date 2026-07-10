import os
import subprocess
import requests
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ========= CONFIGURAÇÕES DA API =========
API_KEY = "SUA_CHAVE_AQUI"  # ⚠️ SUBSTITUA AQUI ou use variável de ambiente
API_URL = "https://api.openai.com/v1/chat/completions"  # Ajuste se for outra API

# ========= FUNÇÕES DA IA =========
def chamar_api(mensagens, temperatura=0.7, max_tokens=500):
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
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Erro na API: {e}"

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
    try:
        if os.name == 'nt':
            processo = subprocess.run(comando, shell=True, capture_output=True, text=True, check=False)
        else:
            processo = subprocess.run(['sh', '-c', comando], capture_output=True, text=True, check=False)
        if processo.returncode == 0:
            return processo.stdout.strip() or "Comando executado com sucesso."
        else:
            return f"Erro: {processo.stderr.strip()}"
    except Exception as e:
        return f"Falha ao executar: {e}"

def identificar_intencao(entrada):
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

# ========= ROTA DO SITE =========
@app.route('/')
def index():
    return render_template('index.html')

# ========= ROTA DA IA (API interna) =========
@app.route('/api/lenior', methods=['POST'])
def lenior_api():
    data = request.json
    mensagem_usuario = data.get('mensagem', '').strip()
    
    if not mensagem_usuario:
        return jsonify({'erro': 'Mensagem vazia'}), 400
    
    # 1. Descobre o que o usuário quer
    intencao = identificar_intencao(mensagem_usuario)
    
    resposta = ""
    tipo_resposta = "texto"  # pode ser 'texto', 'codigo' ou 'comando'
    comando_confirmar = None
    
    if intencao == "codigo":
        tipo_resposta = "codigo"
        resposta = gerar_codigo(mensagem_usuario)
    
    elif intencao == "comando":
        tipo_resposta = "comando"
        # Envia o comando para o front-end pedir confirmação
        comando_confirmar = mensagem_usuario
        resposta = f"Quer executar o comando: '{mensagem_usuario}' ?"
    
    else:  # conversar
        tipo_resposta = "texto"
        resposta = conversar(mensagem_usuario)
    
    return jsonify({
        'resposta': resposta,
        'tipo': tipo_resposta,
        'comando': comando_confirmar  # Se não for None, o front mostra botão de confirmação
    })

# ========= ROTA PARA EXECUTAR COMANDO (após confirmação) =========
@app.route('/api/executar', methods=['POST'])
def executar():
    data = request.json
    comando = data.get('comando', '')
    if not comando:
        return jsonify({'erro': 'Comando vazio'}), 400
    
    resultado = executar_comando(comando)
    return jsonify({'resultado': resultado})

if __name__ == '__main__':
    # Rode em modo debug para testes
    app.run(debug=True, host='0.0.0.0', port=5000)
