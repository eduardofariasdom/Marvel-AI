"""Agente Akinator: adivinha o personagem Marvel que o jogador pensou."""

import json
import re
from typing import Any

from langchain.agents import create_agent

from agents.modelo import MODELO

SYSTEM_PROMPT: str = (
    "Voce e o Scanner da S.H.I.E.L.D., um adivinhador de personagens do "
    "universo Marvel. O jogador pensou em um personagem e voce precisa "
    "descobrir qual e, fazendo perguntas de sim ou nao.\n"
    "\n"
    "Regras:\n"
    "- Faca UMA pergunta por vez, curta, em portugues, respondivel com "
    "sim, nao ou talvez.\n"
    "- Use o historico para eliminar possibilidades: nunca repita uma "
    "pergunta ja feita nem contrarie uma resposta anterior.\n"
    "- Comece por caracteristicas amplas (heroi ou vilao, humano ou nao, "
    "faz parte dos Vingadores) e so depois va para detalhes.\n"
    "- Arrisque um palpite quando tiver confianca alta, ou obrigatoriamente "
    "na pergunta 20.\n"
    "- So existe um universo possivel: personagens da Marvel.\n"
    "\n"
    "Responda SEMPRE com um JSON unico, sem texto fora dele, sem crase e "
    "sem marcacao de codigo:\n"
    '{"tipo": "pergunta", "texto": "A pergunta aqui?"}\n'
    "ou\n"
    '{"tipo": "palpite", "texto": "Voce pensou no Homem de Ferro!", '
    '"personagem": "Homem de Ferro", "personagem_en": "Iron Man"}\n'
    "\n"
    "O campo 'personagem_en' e obrigatorio no palpite: e o nome do personagem "
    "como a Marvel publica em ingles. O app procura a arte dele por esse nome "
    "no catalogo, que so tem nome em ingles; com o nome em portugues a busca "
    "nao acha nada."
)

agent = create_agent(
    model=MODELO,
    tools=[],
    system_prompt=SYSTEM_PROMPT,
)

LIMITE_PERGUNTAS: int = 20


def _texto_da_resposta(resultado: dict[str, Any]) -> str:
    """Extrai o texto da ultima mensagem, lidando com o retorno em blocos do Gemini."""
    conteudo = resultado["messages"][-1].content
    if isinstance(conteudo, list):
        return "".join(
            bloco.get("text", "") if isinstance(bloco, dict) else str(bloco)
            for bloco in conteudo
        ).strip()
    return str(conteudo).strip()


def _extrair_json(bruto: str) -> dict[str, Any] | None:
    """Le o JSON da resposta mesmo que o modelo embrulhe em bloco de codigo."""
    limpo = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    try:
        dados = json.loads(limpo)
    except json.JSONDecodeError:
        # Ultimo recurso: pega o primeiro objeto {...} que aparecer no texto.
        achado = re.search(r"\{.*\}", limpo, flags=re.DOTALL)
        if not achado:
            return None
        try:
            dados = json.loads(achado.group(0))
        except json.JSONDecodeError:
            return None
    return dados if isinstance(dados, dict) else None


def _montar_historico(historico: list[dict[str, str]]) -> str:
    """Transforma as rodadas anteriores em texto para o agente ler."""
    if not historico:
        return "Nenhuma pergunta feita ainda. Faca a primeira."
    linhas = [
        f"{i}. {rodada.get('pergunta', '')} -> {rodada.get('resposta', '')}"
        for i, rodada in enumerate(historico, start=1)
    ]
    return "Perguntas e respostas ate agora:\n" + "\n".join(linhas)


def proxima_jogada(historico: list[dict[str, str]]) -> dict[str, str]:
    """
    Decide a proxima pergunta ou o palpite final.

    Devolve sempre {"tipo", "texto", "personagem", "personagem_en"}.

    `personagem` e o nome em portugues, que vai para a tela; `personagem_en` e
    o nome em ingles, que e por onde o app acha a arte na ComicVine.
    """
    rodadas = len(historico)
    instrucao = _montar_historico(historico)

    if rodadas >= LIMITE_PERGUNTAS - 1:
        instrucao += (
            f"\n\nVoce ja fez {rodadas} perguntas. "
            "De o palpite final agora, obrigatoriamente com tipo 'palpite'."
        )

    try:
        resultado = agent.invoke({"messages": [{"role": "user", "content": instrucao}]})
        dados = _extrair_json(_texto_da_resposta(resultado))
    except Exception:
        dados = None

    if not dados or dados.get("tipo") not in ("pergunta", "palpite"):
        # O jogo nunca pode travar por uma falha do modelo.
        return {
            "tipo": "pergunta",
            "texto": "O personagem que voce pensou e um heroi?",
            "personagem": "",
            "personagem_en": "",
        }

    personagem = str(dados.get("personagem", "")).strip()
    return {
        "tipo": str(dados.get("tipo", "pergunta")),
        "texto": str(dados.get("texto", "")).strip(),
        "personagem": personagem,
        # Se o modelo esquecer o ingles, o portugues ainda e melhor que nada.
        "personagem_en": str(dados.get("personagem_en", "")).strip() or personagem,
    }
