"""Agente Jarvis: responde perguntas do jogador usando o perfil e as tools de busca."""

from langchain.agents import create_agent

from agents.modelo import MODELO
from tools.catalogo_tools import buscar_personagem, buscar_time
from tools.firestore_tools import conceder_xp, consultar_perfil, registrar_poder

SYSTEM_PROMPT: str = (
    "Voce e Jarvis, o assistente de um agente da S.H.I.E.L.D. dentro de um "
    "app de RPG baseado no universo Marvel. Responda sempre em portugues, em "
    "1 a 3 frases, tom confiante e levemente formal. Os dados de perfil do "
    "usuario (nivel, XP, poderes) vem prontos na mensagem - nunca invente "
    "valores que nao estejam la. Use as ferramentas buscar_personagem e "
    "buscar_time apenas quando a pergunta citar um personagem ou time "
    "especifico que nao esteja nos dados ja fornecidos. "
    "Use consultar_perfil quando precisar de um dado do jogador que nao "
    "esteja na mensagem. Use conceder_xp e registrar_poder apenas como "
    "recompensa por algo que o jogador concluiu de fato nesta conversa - "
    "nunca so porque ele pediu."
)

agent = create_agent(
    model=MODELO,
    tools=[buscar_personagem, buscar_time, consultar_perfil, conceder_xp, registrar_poder],
    system_prompt=SYSTEM_PROMPT,
)


def invocar_jarvis(pergunta_com_contexto: str) -> str:
    """Invoca o agente Jarvis e devolve o texto da ultima mensagem."""
    result = agent.invoke(
        {"messages": [{"role": "user", "content": pergunta_com_contexto}]}
    )
    conteudo = result["messages"][-1].content
    if isinstance(conteudo, list):
        # Gemini pode devolver o conteudo em blocos; junta apenas o texto.
        return "".join(
            bloco.get("text", "") if isinstance(bloco, dict) else str(bloco)
            for bloco in conteudo
        ).strip()
    return str(conteudo).strip()
