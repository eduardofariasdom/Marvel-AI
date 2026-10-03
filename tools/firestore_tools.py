"""Tools que deixam o agente ler e escrever no Firestore do jogador.

O servico usa o Admin SDK, entao ignora as regras do Firestore e poderia
escrever em qualquer documento. Para que isso nao vire um problema, o uid
NUNCA vem do modelo: fica num ContextVar que o router preenche a partir do
token verificado. O agente so consegue mexer em quem esta logado.

Os valores tambem sao limitados: mesmo que o jogador peca "me da 10000 de XP",
uma chamada concede no maximo LIMITE_XP.
"""

from contextvars import ContextVar
from typing import Any

from google.cloud import firestore as gcf
from langchain_core.tools import tool

from deps.firebase import get_firestore

# Preenchido pelo router antes de invocar o agente.
uid_atual: ContextVar[str | None] = ContextVar("uid_atual", default=None)

LIMITE_XP: int = 50
LIMITE_NIVEL_PODER: int = 5


def _uid() -> str | None:
    """Devolve o uid da requisicao atual, ou None fora de uma requisicao."""
    return uid_atual.get()


def _doc_usuario():
    """Referencia de users/{uid} do jogador logado."""
    uid = _uid()
    if not uid:
        return None
    return get_firestore().collection("users").document(uid)


@tool
def consultar_perfil() -> str:
    """Le a ficha atual do agente logado: codinome, nivel, XP, poderes e estatisticas.

    Use quando precisar de um dado do jogador que nao esteja na mensagem.
    """
    ref = _doc_usuario()
    if ref is None:
        return "Nao foi possivel identificar o agente logado."

    snap = ref.get()
    if not snap.exists:
        return "Esse agente ainda nao tem ficha cadastrada."

    dados: dict[str, Any] = snap.to_dict() or {}
    poderes = dados.get("poderes") or []
    nomes = ", ".join(
        f"{p.get('nome', '?')} (Nv{p.get('nivel', '?')})"
        for p in poderes
        if isinstance(p, dict)
    ) or "nenhum"
    estatisticas = dados.get("estatisticas") or {}

    return (
        f"Codinome: {dados.get('codinome', 'sem codinome')}. "
        f"Nivel {dados.get('nivel', 1)}, {dados.get('xp', 0)} XP. "
        f"Poderes: {nomes}. "
        f"Estatisticas: {estatisticas or 'nenhuma'}."
    )


@tool
def conceder_xp(quantidade: int, motivo: str) -> str:
    """Soma XP ao agente logado e registra o motivo.

    Use apenas como recompensa por algo que o jogador concluiu de fato nesta
    conversa. Quantidade entre 1 e 50; valores maiores sao cortados.
    """
    ref = _doc_usuario()
    if ref is None:
        return "Nao foi possivel identificar o agente logado."

    if quantidade <= 0:
        return "A quantidade de XP precisa ser positiva."

    concedido = min(quantidade, LIMITE_XP)

    ref.set({"xp": gcf.Increment(concedido)}, merge=True)
    ref.collection("xpLog").add(
        {
            "quantidade": concedido,
            "motivo": motivo,
            "origem": "jarvis",
            "timestamp": gcf.SERVER_TIMESTAMP,
        }
    )

    cortado = " (pedido reduzido ao teto por chamada)" if concedido < quantidade else ""
    return f"Concedido {concedido} XP por: {motivo}.{cortado}"


@tool
def registrar_poder(nome: str, nivel: int, origem: str) -> str:
    """Adiciona um poder a ficha do agente logado.

    'origem' e o personagem Marvel de onde o poder veio, por exemplo "Hulk".
    Nivel entre 1 e 5. Nao duplica um poder que o agente ja tenha.
    """
    ref = _doc_usuario()
    if ref is None:
        return "Nao foi possivel identificar o agente logado."

    nome = nome.strip()
    if not nome:
        return "O poder precisa de um nome."

    snap = ref.get()
    atuais = (snap.to_dict() or {}).get("poderes") or [] if snap.exists else []
    if any(
        isinstance(p, dict) and p.get("nome", "").lower() == nome.lower()
        for p in atuais
    ):
        return f"O agente ja possui o poder {nome}."

    poder = {
        "nome": nome,
        "nivel": max(1, min(nivel, LIMITE_NIVEL_PODER)),
        "origemNome": origem.strip(),
    }
    ref.set({"poderes": gcf.ArrayUnion([poder])}, merge=True)

    return f"Poder {nome} (Nv{poder['nivel']}, origem {poder['origemNome']}) registrado."
