"""Tools de consulta ao catalogo de personagens e times.

Usam o mesmo caminho do app: ComicVine primeiro, Firestore como cache e
fallback. Ver tools/catalogo_servico.py.
"""

from langchain_core.tools import tool

from tools import catalogo_servico

LIMITE: int = 3


@tool
def buscar_personagem(nome: str) -> str:
    """Busca um personagem da Marvel pelo nome e devolve poderes e descricao.

    Use quando a pergunta citar um heroi ou vilao especifico que nao esteja
    nos dados de perfil ja fornecidos na mensagem.
    """
    try:
        achados = catalogo_servico.buscar_personagens(nome, LIMITE)
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
        achados = catalogo_servico.buscar_times(nome, LIMITE)
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
