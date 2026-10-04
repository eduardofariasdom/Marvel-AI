"""Agente narrador: transforma os numeros do turno em duas frases."""

import json
import re
from typing import Any

from langchain.agents import create_agent

from agents.modelo import MODELO

SYSTEM_PROMPT: str = (
    "Voce narra turnos de batalha de RPG entre super-herois Marvel, em "
    "portugues do Brasil.\n"
    "\n"
    "Recebe os numeros de UM turno e devolve DUAS frases curtas: a acao do "
    "agente e o revide do oponente. Cada frase tem no maximo 16 palavras.\n"
    "\n"
    "Regras que nao podem ser quebradas:\n"
    "- Use os numeros exatos de dano que vierem. Nunca invente outro.\n"
    "- Se o alvo ESQUIVOU, o golpe errou: nao cite dano nenhum nessa frase.\n"
    "- Nunca escreva os nomes dos campos (dano, esquiva, critico) na frase. "
    "Narre, nao relate.\n"
    "- Nao decida quem vence a batalha; isso ja foi calculado.\n"
    "- Se nao houver revide (o oponente caiu), devolva string vazia em "
    "'oponente'.\n"
    "\n"
    "Responda SEMPRE com um JSON unico, sem crase e sem marcacao de codigo:\n"
    '{"agente": "frase da acao do agente", "oponente": "frase do revide"}'
)

agent = create_agent(model=MODELO, tools=[], system_prompt=SYSTEM_PROMPT)


def _texto(resultado: dict[str, Any]) -> str:
    """Extrai o texto da ultima mensagem, lidando com retorno em blocos."""
    conteudo = resultado["messages"][-1].content
    if isinstance(conteudo, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in conteudo
        ).strip()
    return str(conteudo).strip()


def _extrair_json(bruto: str) -> dict[str, Any] | None:
    """Le o JSON mesmo que o modelo embrulhe em bloco de codigo."""
    limpo = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    try:
        dados = json.loads(limpo)
    except json.JSONDecodeError:
        achado = re.search(r"\{.*\}", limpo, flags=re.DOTALL)
        if not achado:
            return None
        try:
            dados = json.loads(achado.group(0))
        except json.JSONDecodeError:
            return None
    return dados if isinstance(dados, dict) else None


def _descrever(
    nome_jogador: str,
    nome_oponente: str,
    acao: str,
    dano: int,
    esquivou: bool,
    critico: bool,
    dano_recebido: int,
    jogador_esquivou: bool,
    oponente_caiu: bool,
) -> str:
    """Monta o enunciado do turno, ja resolvendo o caso de esquiva."""
    if esquivou:
        linha_agente = f"{nome_jogador} tenta {acao}, mas {nome_oponente} esquiva."
    else:
        extra = " Acerto critico." if critico else ""
        linha_agente = (
            f"{nome_jogador} acerta {acao} em {nome_oponente}, "
            f"causando {dano} de dano.{extra}"
        )

    if oponente_caiu:
        linha_oponente = f"{nome_oponente} cai. Nao ha revide."
    elif jogador_esquivou:
        linha_oponente = f"{nome_oponente} contra-ataca, mas {nome_jogador} desvia."
    else:
        linha_oponente = (
            f"{nome_oponente} revida e causa {dano_recebido} de dano em {nome_jogador}."
        )

    return f"{linha_agente}\n{linha_oponente}"


def narrar_turno(
    nome_jogador: str,
    nome_oponente: str,
    acao: str,
    dano: int,
    esquivou: bool,
    critico: bool = False,
    dano_recebido: int = 0,
    jogador_esquivou: bool = False,
    oponente_caiu: bool = False,
) -> tuple[str, str]:
    """
    Narra o turno e devolve (frase do agente, frase do oponente).

    A frase do oponente vem vazia quando ele caiu. Qualquer falha cai no
    enunciado deterministico: a batalha nunca trava por causa da IA.
    """
    enunciado = _descrever(
        nome_jogador, nome_oponente, acao, dano, esquivou, critico,
        dano_recebido, jogador_esquivou, oponente_caiu,
    )

    reserva_agente, reserva_oponente = enunciado.split("\n")
    if oponente_caiu:
        reserva_oponente = ""

    try:
        resultado = agent.invoke({"messages": [{"role": "user", "content": enunciado}]})
        dados = _extrair_json(_texto(resultado))
    except Exception:
        dados = None

    if not dados:
        return reserva_agente, reserva_oponente

    agente_txt = str(dados.get("agente", "")).strip() or reserva_agente
    oponente_txt = str(dados.get("oponente", "")).strip()

    if oponente_caiu:
        oponente_txt = ""
    elif not oponente_txt:
        oponente_txt = reserva_oponente

    return agente_txt, oponente_txt
