"""Agente narrador de batalha: transforma os numeros do turno em uma frase dramatica."""

from langchain.agents import create_agent

from agents.modelo import MODELO

SYSTEM_PROMPT: str = (
    "Voce narra turnos de batalha de RPG entre super-herois Marvel, em "
    "portugues, em UMA frase curta e dramatica (maximo 20 palavras). Use os "
    "numeros exatos fornecidos (dano, nome do poder) sem altera-los. Nao "
    "decida quem vence - isso ja foi calculado. Apenas narre a acao deste "
    "turno especificamente."
)

agent = create_agent(
    model=MODELO,
    tools=[],
    system_prompt=SYSTEM_PROMPT,
)


def narrar_turno(entrada: str) -> str:
    """Invoca o narrador e devolve a frase do turno."""
    result = agent.invoke({"messages": [{"role": "user", "content": entrada}]})
    conteudo = result["messages"][-1].content
    if isinstance(conteudo, list):
        return "".join(
            bloco.get("text", "") if isinstance(bloco, dict) else str(bloco)
            for bloco in conteudo
        ).strip()
    return str(conteudo).strip()
