import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import re
import random
import io
import urllib.parse
import tempfile
import asyncio
import edge_tts
import requests
import threading
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# --- CONFIGURAÇÃO DA CHAVE DE API ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
    CONEXAO_OK = True
except:
    API_KEY = ""
    CONEXAO_OK = False

st.set_page_config(page_title="Coach Suprabio", page_icon="🏆", layout="centered")

# --- CSS E ESTILOS ---
st.markdown("""
<style>
    .cliente-box { padding: 15px; border-radius: 10px; background-color: #f0f2f6; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .vendedor-box { padding: 15px; border-radius: 10px; background-color: #e8f4f8; border-right: 5px solid #0088cc; margin-bottom: 10px; text-align: right; }
    .titulo-central { text-align: center; font-size: 2.2em; font-weight: 800; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAÇÕES DO MÉTODO CLAMED ---
MODELO_IA = "models/gemini-2.5-flash"
METODO_CLAMED_PROMPT = """
Aja como um gerente de treinamento da CLAMED. Avalie o atendimento do colaborador com base no método "A PONTE":
1. ABORDE POSITIVAMENTE: Foi ágil, empático e solícito?
2. PESQUISE O CLIENTE: Investigou a necessidade real com perguntas?
3. DEMONSTRAÇÃO ENVOLVENTE: Apresentou a solução focando nos benefícios?
4. NEGOCIE E NEUTRALIZE OBJEÇÕES: Demonstrou empatia ao lidar com objeções (preço/dúvida)?
5. TOME A INICIATIVA (FECHAMENTO): Fechou a venda ativamente (sem esperar o cliente decidir)?
6. ESTENDA O RELACIONAMENTO: Agradeceu, fidelizou e ofereceu cadastro?

Avalie também as ATITUDES VENCEDORAS: Entusiasmo, foco em metas e resiliência.
Dê uma nota de 0 a 10. Forneça um feedback estruturado citando as etapas da PONTE.
"""

# --- DADOS E CASOS ---
ARQUIVO_HISTORICO = "historico_treinamento.xlsx"
ARQUIVO_EQUIPE = "equipe.csv"
CASOS_REAIS = [
    {"queixa": "Moça, eu ando muito esquecido, a cabeça parece que não funciona direito e tô sem energia mental.", "produto_alvo": "Magnésio Dimalato", "prompt_img": "portrait of a stressed middle-aged brazilian man", "genero": "M", "idade": "adulto"},
    {"queixa": "Minha mãe tem 68 anos e está comendo muito mal. Quase não come carne e tá ficando muito fraquinha.", "produto_alvo": "Suprabio 50+", "prompt_img": "portrait of an elderly brazilian woman", "genero": "F", "idade": "idoso"},
    {"queixa": "Tive dengue faz uns meses e agora meu cabelo tá caindo aos tufos, tô ficando desesperada.", "produto_alvo": "Suprabio Cabelos e Unhas", "prompt_img": "portrait of a young brazilian woman looking distressed", "genero": "F", "idade": "jovem"}
]

# --- FUNÇÕES ---
def carregar_equipe():
    if os.path.exists(ARQUIVO_EQUIPE): return pd.read_csv(ARQUIVO_EQUIPE)['Nome'].tolist()
    return ["André", "Bruna", "Eliana", "Leticia", "Marcella", "Jessica", "Diego", "Anderson"]

def transcrever_audio_para_texto(audio_file):
    with st.spinner("🎧 Transcrevendo..."):
        try:
            model = genai.GenerativeModel(MODELO_IA)
            res = model.generate_content(["Transcreva este áudio de atendimento de farmácia.", {"mime_type": "audio/wav", "data": audio_file.getvalue()}])
            return res.text.strip()
        except: return None

def gerar_audio_cliente(texto, genero="F"):
    voz = "pt-BR-AntonioNeural" if genero == "M" else "pt-BR-FranciscaNeural"
    resultado = []
    def worker():
        async def _gerar():
            communicate = edge_tts.Communicate(texto, voz)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp: await communicate.save(fp.name); return fp.name
        try: resultado.append(asyncio.run(_gerar()))
        except: pass
    t = threading.Thread(target=worker); t.start(); t.join()
    with open(resultado[0], "rb") as f: data = f.read()
    os.remove(resultado[0]); return data

# --- ESTADO ---
if "equipe" not in st.session_state: st.session_state.equipe = carregar_equipe()
if "historico_chat" not in st.session_state: st.session_state.historico_chat = []
if "casos_disponiveis" not in st.session_state: st.session_state.casos_disponiveis = CASOS_REAIS.copy()

# --- INTERFACE ---
st.markdown("<div class='titulo-central'>🏆 💊 Coach Suprabio - Método CLAMED 🧠</div>", unsafe_allow_html=True)
colaborador = st.selectbox("Selecione o Vendedor:", ["Selecione..."] + st.session_state.equipe)

if colaborador != "Selecione...":
    if not st.session_state.historico_chat:
        if st.button("🔔 CHAMAR PRÓXIMO CLIENTE"):
            if not st.session_state.casos_disponiveis: st.session_state.casos_disponiveis = CASOS_REAIS.copy()
            caso = random.choice(st.session_state.casos_disponiveis); st.session_state.casos_disponiveis.remove(caso)
            st.session_state.caso_atual = caso
            st.session_state.historico_chat = [{"role": "Cliente", "text": caso["queixa"], "audio": gerar_audio_cliente(caso["queixa"], caso["genero"])}]
            st.session_state.turno = 1; st.session_state.feedback = ""; st.rerun()
    else:
        for msg in st.session_state.historico_chat:
            if msg["role"] == "Cliente": st.markdown(f"<div class='cliente-box'>🗣️ {msg['text']}</div>", unsafe_allow_html=True); st.audio(msg["audio"], format="audio/mpeg")
            else: st.markdown(f"<div class='vendedor-box'>🧑‍⚕️ {msg['text']}</div>", unsafe_allow_html=True)

        if not st.session_state.feedback:
            resposta_texto = st.text_area("Sua resposta:", key=f"t{st.session_state.turno}")
            audio_val = st.audio_input("Gravar áudio", key=f"a{st.session_state.turno}")
            if st.button("Enviar"):
                resp = transcrever_audio_para_texto(audio_val) if audio_val else resposta_texto
                st.session_state.historico_chat.append({"role": "Vendedor", "text": resp})
                model = genai.GenerativeModel(MODELO_IA)
                res = model.generate_content(f"Histórico: {st.session_state.historico_chat}. Responda como cliente objetando.").text
                st.session_state.historico_chat.append({"role": "Cliente", "text": res, "audio": gerar_audio_cliente(res, st.session_state.caso_atual["genero"])})
                st.session_state.turno += 1; st.rerun()

            if st.button("Finalizar e Avaliar"):
                texto_final = "\n".join([f"{m['role']}: {m['text']}" for m in st.session_state.historico_chat])
                res = genai.GenerativeModel(MODELO_IA).generate_content(f"{METODO_CLAMED_PROMPT}\n\nAtendimento:\n{texto_final}").text
                st.session_state.feedback = res; st.rerun()

        if st.session_state.feedback:
            st.info(st.session_state.feedback)
            if st.button("💾 Salvar Treino"):
                salvar_sessao({"Data": datetime.now(), "Colaborador": colaborador, "FeedbackIA": st.session_state.feedback})
                st.session_state.historico_chat = []; st.rerun()