"""Catalogo de personagens e times, com a ComicVine na frente do Firestore.

Ordem de busca:

1. ComicVine, se a chave existir. E a fonte oficial: nome real, descricao,
   poderes, times e imagem.
2. O resultado e gravado no Firestore, que e cache puro da ComicVine - nao
   ha catalogo escrito a mao em lugar nenhum.
4. Se a ComicVine estiver fora (sem chave, 403, limite de requisicoes), cai
   direto no Firestore. A busca nunca fica sem resposta.

O app mobile consome isto pelo router /catalogo, para a chave da ComicVine
ficar so no servidor.
"""

from typing import Any

from deps.firebase import get_firestore
from tools import comicvine

LIMITE_PADRAO = 10


def _do_firestore(colecao: str, termo: str, limite: int) -> list[dict[str, Any]]:
    """Busca por prefixo em `nomeBusca`. Termo vazio devolve o inicio da colecao."""
    alvo = comicvine.chave_busca(termo)
    consulta = get_firestore().collection(colecao).order_by("nomeBusca")
    if alvo:
        consulta = consulta.start_at([alvo]).end_at([alvo + ""])
    return [d.to_dict() or {} for d in consulta.limit(limite).get()]


def _cachear(colecao: str, achados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grava o que veio da ComicVine, para a proxima busca nao gastar cota."""
    db = get_firestore()
    lote = db.batch()
    for item in achados:
        lote.set(db.collection(colecao).document(item["nomeBusca"]), item, merge=True)
    if achados:
        lote.commit()
    return achados


def buscar_personagens(termo: str, limite: int = LIMITE_PADRAO) -> list[dict[str, Any]]:
    """Personagens pela ComicVine, com o Firestore como rede de seguranca."""
    if comicvine.disponivel() and termo.strip():
        try:
            achados = comicvine.buscar_personagens(termo, limite)
            if achados:
                return _cachear("personagens", achados)
        except Exception:
            # Chave invalida, 403, limite de requisicoes: cai para o local.
            pass
    return _do_firestore("personagens", termo, limite)


def buscar_times(termo: str, limite: int = LIMITE_PADRAO) -> list[dict[str, Any]]:
    """Times pela ComicVine, com o Firestore como rede de seguranca."""
    if comicvine.disponivel() and termo.strip():
        try:
            achados = comicvine.buscar_times(termo, limite)
            if achados:
                return _cachear("times", achados)
        except Exception:
            pass
    return _do_firestore("times", termo, limite)
