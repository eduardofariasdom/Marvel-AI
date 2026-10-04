"""Cliente da ComicVine, a fonte oficial de dados dos personagens.

A ComicVine traz nome real, descricao, poderes, times e imagem - tudo melhor
que o seed. O que ela NAO tem e o que o jogo precisa: se o personagem e heroi
ou vilao e qual o nivel de ameaca. Por isso o resultado e mesclado com o
documento que ja exista no Firestore, que guarda essa parte do jogo.

Chave gratuita em https://comicvine.gamespot.com/api/ (precisa de conta).
Sem COMICVINE_API_KEY definida, `disponivel()` devolve False e quem chama cai
no catalogo local.

A API exige User-Agent proprio: sem ele a resposta e 403.
"""

import os
import unicodedata
from typing import Any

import httpx

BASE = "https://comicvine.gamespot.com/api"
USER_AGENT = "MarvelRPG/1.0 (projeto academico)"
TIMEOUT = 15.0

# Pedir so o que usamos deixa a resposta muito menor.
CAMPOS_PERSONAGEM = (
    "name,real_name,deck,image,powers,teams,publisher,count_of_issue_appearances"
)
CAMPOS_TIME = "name,deck,image,characters,publisher,count_of_isssue_appearances"


def disponivel() -> bool:
    """Diz se a chave da ComicVine esta configurada."""
    return bool(os.getenv("COMICVINE_API_KEY", "").strip())


def chave_busca(nome: str) -> str:
    """Minusculas e sem acento, igual ao `nomeBusca` do Firestore."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    return sem_acento.lower().strip()


def _get(recurso: str, campos: str, termo: str, limite: int) -> list[dict[str, Any]]:
    """Chama a ComicVine e devolve a lista crua de resultados."""
    resposta = httpx.get(
        f"{BASE}/{recurso}/",
        params={
            "api_key": os.environ["COMICVINE_API_KEY"],
            "format": "json",
            "filter": f"name:{termo}",
            "field_list": campos,
            "limit": limite,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
    )
    resposta.raise_for_status()
    corpo = resposta.json()

    # A ComicVine responde 200 mesmo em erro de negocio; o status real vem aqui.
    if corpo.get("status_code") != 1:
        raise RuntimeError(f"ComicVine recusou: {corpo.get('error', 'erro desconhecido')}")

    return corpo.get("results") or []


def _so_marvel(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A ComicVine cobre todas as editoras; aqui so interessa a Marvel."""
    marvel = [
        i for i in itens
        if "marvel" in ((i.get("publisher") or {}).get("name") or "").lower()
    ]
    # Se nada bater a editora, devolve tudo em vez de uma lista vazia.
    return marvel or itens


def _nomes(valor: Any) -> list[str]:
    """Extrai os `name` de uma lista de objetos da ComicVine."""
    if not isinstance(valor, list):
        return []
    return [i.get("name", "") for i in valor if isinstance(i, dict) and i.get("name")]


def _ameaca_por_poderes(qtd: int) -> str:
    """A ComicVine nao tem nivel de ameaca; derivamos da quantidade de poderes."""
    if qtd >= 6:
        return "alta"
    if qtd >= 3:
        return "media"
    return "baixa"


# A ComicVine tambem nao marca heroi/vilao. O que ela da e o `deck`, um resumo
# em ingles escrito por editores. Estas palavras aparecem em quem e antagonista.
MARCAS_DE_VILAO: tuple[str, ...] = (
    "villain", "supervillain", "criminal", "crime lord", "enemy of",
    "nemesis", "antagonist", "terrorist", "warlord", "mercenary",
    "assassin", "tyrant", "conqueror", "foe of",
)


def _parece_vilao(deck: str) -> bool:
    """Heuristica sobre o texto da propria ComicVine, nao sobre lista minha.

    Erra em personagens ambiguos (Loki, Venom, Gamora mudam de lado). E o que
    da para fazer sem um campo de alinhamento na API.
    """
    texto = deck.lower()
    return any(m in texto for m in MARCAS_DE_VILAO)


def buscar_personagens(termo: str, limite: int = 10) -> list[dict[str, Any]]:
    """Busca personagens e devolve no formato da colecao `personagens`."""
    saida: list[dict[str, Any]] = []
    for p in _so_marvel(_get("characters", CAMPOS_PERSONAGEM, termo, limite)):
        nome = p.get("name") or ""
        if not nome:
            continue
        poderes = _nomes(p.get("powers"))
        saida.append(
            {
                "nome": nome,
                "nomeBusca": chave_busca(nome),
                "alterEgo": p.get("real_name") or "",
                "deck": p.get("deck") or "",
                "poderes": poderes,
                "times": _nomes(p.get("teams")),
                "imagem": (p.get("image") or {}).get("medium_url") or "",
                "aparicoes": p.get("count_of_issue_appearances") or 0,
                # Deduzidos do conteudo da ComicVine; ver _parece_vilao.
                "heroi": not _parece_vilao(p.get("deck") or ""),
                "ameaca": _ameaca_por_poderes(len(poderes)),
                "fonte": "comicvine",
            }
        )
    return saida


def buscar_times(termo: str, limite: int = 10) -> list[dict[str, Any]]:
    """Busca times e devolve no formato da colecao `times`."""
    saida: list[dict[str, Any]] = []
    for t in _so_marvel(_get("teams", CAMPOS_TIME, termo, limite)):
        nome = t.get("name") or ""
        if not nome:
            continue
        saida.append(
            {
                "nome": nome,
                "nomeBusca": chave_busca(nome),
                "deck": t.get("deck") or "",
                "membros": _nomes(t.get("characters"))[:12],
                "imagem": (t.get("image") or {}).get("medium_url") or "",
                "fonte": "comicvine",
            }
        )
    return saida
