"""Tools de consulta ao catalogo de personagens e times.

Nao existe backend Node: o catalogo mora no proprio Firestore, nas colecoes
`personagens` e `times`, e o app mobile le as mesmas colecoes. Aqui usamos o
Admin SDK, entao a leitura ignora as regras.
"""

from typing import Any

from langchain_core.tools import tool

from deps.firebase import get_firestore

LIMITE: int = 3


def _buscar(colecao: str, termo: str) -> list[dict[str, Any]]:
    """Busca por prefixo no campo `nomeBusca` (nome em minusculas, sem acento).

    O Firestore nao tem busca textual: o truque do prefixo e range com \\uf8ff,
    que casa qualquer sufixo. Por isso o documento guarda `nomeBusca` pronto.
    """
    alvo = termo.strip().lower()
    if not alvo:
        return []

    docs = (
        get_firestore()
        .collection(colecao)
        .order_by("nomeBusca")
        .start_at([alvo])
        .end_at([alvo + ""])
        .limit(LIMITE)
        .get()
    )
    return [d.to_dict() or {} for d in docs]


@tool
def buscar_personagem(nome: str) -> str:
    """Busca um personagem da Marvel pelo nome e devolve poderes e descricao.

    Use quando a pergunta citar um heroi ou vilao especifico que nao esteja
    nos dados de perfil ja fornecidos na mensagem.
    """
    try:
        achados = _buscar("personagens", nome)
    except Exception as exc:
        return f"Nao foi possivel consultar o catalogo: {exc}"

    if not achados:
        return f"Nenhum personagem encontrado para '{nome}'."

    linhas = []
    for p in achados:
        poderes = ", ".join(p.get("poderes") or []) or "nao informados"
        linhas.append(
            f"- {p.get('nome', 'Desconhecido')} | Poderes: {poderes} | "
            f"{p.get('deck', 'sem descricao')}"
        )
    return f"Resultados para '{nome}':\n" + "\n".join(linhas)


@tool
def buscar_time(nome: str) -> str:
    """Busca um time da Marvel pelo nome e lista os membros conhecidos.

    Use quando a pergunta citar um grupo especifico (Vingadores, X-Men, etc.)
    que nao esteja nos dados ja fornecidos.
    """
    try:
        achados = _buscar("times", nome)
    except Exception as exc:
        return f"Nao foi possivel consultar o catalogo: {exc}"

    if not achados:
        return f"Nenhum time encontrado para '{nome}'."

    linhas = []
    for t in achados:
        membros = ", ".join(t.get("membros") or []) or "nao informados"
        linhas.append(
            f"- {t.get('nome', 'Desconhecido')} | Membros: {membros} | "
            f"{t.get('deck', 'sem descricao')}"
        )
    return f"Resultados para '{nome}':\n" + "\n".join(linhas)
