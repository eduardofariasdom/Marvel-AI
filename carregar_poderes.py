#!/usr/bin/env python3
"""Dataload dos poderes da ComicVine para o Firestore.

A ComicVine tem 128 poderes no catalogo (/powers/), e o endpoint devolve 100
por pagina: duas chamadas resolvem. Cada poder vira um documento na colecao
`poderes`, que o app le para montar loadout e recompensa de batalha.

    $env:COMICVINE_API_KEY = "sua_chave"
    python carregar_poderes.py

Opcional, mais pesado: `--com-personagens N` tambem baixa os N personagens
mais classicos da Marvel com os poderes de cada um, para a batalha saber o que
o oponente pode largar ao ser derrotado. Cada personagem custa 1 requisicao,
e o limite da ComicVine e 200 por hora.
"""

import argparse
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import json
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from deps.firebase import get_firestore  # noqa: E402  (precisa do .env carregado)

BASE = "https://comicvine.gamespot.com/api"
USER_AGENT = "MarvelRPG/1.0 (projeto academico)"
PAGINA = 100
PAUSA = 1.0  # segundos entre chamadas, para nao irritar a API


def chave_busca(nome: str) -> str:
    """Minusculas, sem acento e sem barra: id do documento e busca por prefixo.

    O Firestore trata "/" como separador de caminho, entao nomes como
    "Shape-Shifting/Morphing" quebrariam o documento. Tambem nao pode ser
    vazio nem comecar com ponto.
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[/\.\[\]*#?]+", "-", sem_acento.lower()).strip(" -")
    return limpo or "sem-nome"


def api(recurso: str, **params: Any) -> dict[str, Any]:
    """Chama a ComicVine e devolve o corpo ja validado."""
    chave = os.getenv("COMICVINE_API_KEY", "").strip()
    if not chave:
        sys.exit("COMICVINE_API_KEY nao definida.")

    params.update({"api_key": chave, "format": "json"})
    url = f"{BASE}/{recurso}/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    corpo = json.load(urllib.request.urlopen(req, timeout=60))

    # A ComicVine responde 200 mesmo em erro; o status real vem aqui.
    if corpo.get("status_code") != 1:
        sys.exit(f"ComicVine recusou: {corpo.get('error')}")
    return corpo


def nivel_por_raridade(posicao: int, total: int) -> int:
    """
    Nivel 1 a 5 pela posicao no catalogo.

    A ComicVine numera os poderes por ordem de cadastro, e os primeiros sao os
    mais comuns (Voo, Super Forca, Agilidade). Os do fim sao raros, entao valem
    mais no jogo. Nao e dado da API: e a regra do RPG, e so mora aqui.
    """
    faixa = posicao / max(total, 1)
    if faixa > 0.85:
        return 5
    if faixa > 0.65:
        return 4
    if faixa > 0.40:
        return 3
    if faixa > 0.20:
        return 2
    return 1


def carregar_poderes() -> list[dict[str, Any]]:
    """Baixa os 128 poderes, paginando de 100 em 100."""
    poderes: list[dict[str, Any]] = []
    offset = 0

    while True:
        corpo = api("powers", limit=PAGINA, offset=offset,
                    field_list="id,name,deck,description")
        lote = corpo.get("results") or []
        poderes.extend(lote)

        total = corpo.get("number_of_total_results", 0)
        offset += len(lote)
        print(f"   {offset}/{total}")
        if offset >= total or not lote:
            break
        time.sleep(PAUSA)

    return poderes


def gravar_poderes(poderes: list[dict[str, Any]]) -> None:
    """Grava a colecao `poderes` em lotes (o Firestore aceita 500 por lote)."""
    db = get_firestore()
    total = len(poderes)
    lote = db.batch()

    for i, p in enumerate(poderes):
        nome = (p.get("name") or "").strip()
        if not nome:
            continue
        doc = {
            "comicVineId": p.get("id", 0),
            "nome": nome,
            "nomeBusca": chave_busca(nome),
            "deck": (p.get("deck") or "").strip(),
            "nivelBase": nivel_por_raridade(i, total),
            "fonte": "comicvine",
        }
        lote.set(db.collection("poderes").document(chave_busca(nome)), doc, merge=True)

        if (i + 1) % 400 == 0:
            lote.commit()
            lote = db.batch()

    lote.commit()


def carregar_personagens(quantos: int) -> int:
    """
    Baixa os N personagens mais classicos com os poderes de cada um.

    Os poderes so vem no endpoint de detalhe, entao e 1 requisicao por
    personagem — por isso fica atras de uma flag.
    """
    db = get_firestore()

    elenco = api("publisher/4010-31", field_list="characters")
    ids = [c["id"] for c in (elenco["results"].get("characters") or [])[:quantos]]
    print(f"   elenco: {len(ids)} personagens")

    gravados = 0
    for n, cid in enumerate(ids, start=1):
        try:
            corpo = api(
                f"character/4005-{cid}",
                field_list="id,name,real_name,deck,image,powers,teams,"
                           "count_of_issue_appearances",
            )
        except Exception as e:
            print(f"   ! {cid}: {e}")
            continue

        r = corpo.get("results") or {}
        nome = (r.get("name") or "").strip()
        if not nome:
            continue

        poderes = [x["name"] for x in (r.get("powers") or []) if x.get("name")]
        aparicoes = r.get("count_of_issue_appearances") or 0

        db.collection("personagens").document(chave_busca(nome)).set(
            {
                "comicVineId": r.get("id", 0),
                "nome": nome,
                "nomeBusca": chave_busca(nome),
                "alterEgo": r.get("real_name") or "",
                "deck": r.get("deck") or "",
                "poderes": poderes,
                "times": [t["name"] for t in (r.get("teams") or []) if t.get("name")],
                "imagem": (r.get("image") or {}).get("medium_url") or "",
                "aparicoes": aparicoes,
                "ameaca": "alta" if aparicoes >= 2500 else "media" if aparicoes >= 600 else "baixa",
                "fonte": "comicvine",
            },
            merge=True,
        )
        gravados += 1
        print(f"   {n}/{len(ids)} {nome} ({len(poderes)} poderes)")
        time.sleep(PAUSA)

    return gravados


def main() -> None:
    p = argparse.ArgumentParser(description="Dataload da ComicVine para o Firestore.")
    p.add_argument(
        "--com-personagens", type=int, default=0, metavar="N",
        help="tambem baixa N personagens com os poderes de cada um (1 requisicao cada)",
    )
    args = p.parse_args()

    print("== poderes ==")
    poderes = carregar_poderes()
    gravar_poderes(poderes)
    print(f"   {len(poderes)} poderes gravados na colecao `poderes`")

    if args.com_personagens:
        print(f"\n== personagens (ate {args.com_personagens}) ==")
        n = carregar_personagens(args.com_personagens)
        print(f"   {n} personagens gravados com seus poderes")

    print("\nPronto. O app ja enxerga tudo.")


if __name__ == "__main__":
    main()
