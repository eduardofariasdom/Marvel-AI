"""Modelo de linguagem usado por todos os agentes.

Fica num lugar so para trocar de provedor sem mexer em tres arquivos.
O formato e "<provedor>:<modelo>", lido pelo init_chat_model do LangChain.

Groq precisa da variavel GROQ_API_KEY no ambiente.
"""

import os

from dotenv import load_dotenv

# Carregado aqui, e nao so no main.py: os agentes constroem o cliente do Groq
# na hora do import, antes de qualquer linha do main rodar. Sem isto o
# servico sobe sem GROQ_API_KEY e morre no boot.
load_dotenv()

# gpt-oss-120b (servido pelo Groq) faz tool calling, que o Jarvis usa.
# Alternativa mais leve: "groq:openai/gpt-oss-20b".
MODELO: str = os.getenv("MODELO_IA", "groq:openai/gpt-oss-120b")
