#!/usr/bin/env python3
"""Concede poderes a um agente, para testar o app sem ter que vencer batalhas.

Faz exatamente o que o jogo faz ao vencer: pega um poder de um personagem do
catalogo, com o nivel vindo da colecao `poderes`. Nada e inventado — os nomes
sao da ComicVine e os niveis do dataload.

    python dar_poderes.py --email alguem@exemplo.com --quantos 12

Usa o Admin SDK (service account), entao nao precisa da senha de ninguem.
"""

import argparse
import random
import sys
import unicodedata
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from firebase_admin import auth  # noqa: E402
from deps.firebase import get_firestore  # noqa: E402


def chave(nome: str) -> str:
    """Mesma normalizacao do dataload e do app."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[/\\.\[\]*#?]+", "-", sem_acento.lower()).strip(" -")
    return limpo or "sem-nome"


def niveis_do_catalogo(db: Any) -> dict[str, int]:
    """nome em minusculas -> nivelBase, lido uma vez so."""
    mapa: dict[str, int] = {}
    for d in db.collection("poderes").limit(500).get():
        x = d.to_dict() or {}
        nome = x.get("nome")
        if nome:
            mapa[nome.lower()] = int(x.get("nivelBase") or 1)
    return mapa


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--quantos", type=int, default=12)
    p.add_argument("--zerar", action="store_true",
                   help="apaga os poderes atuais antes de conceder")
    args = p.parse_args()

    db = get_firestore()

    try:
        usuario = auth.get_user_by_email(args.email)
    except Exception as e:
        sys.exit(f"Usuario nao encontrado: {e}")

    uid = usuario.uid
    print(f"agente: {args.email}")
    print(f"uid: {uid}")

    ref = db.collection("users").document(uid)
    snap = ref.get()
    if not snap.exists:
        sys.exit("Esse uid nao tem ficha em users/. Entre no app uma vez primeiro.")

    perfil = snap.to_dict() or {}
    atuais = [] if args.zerar else (perfil.get("poderes") or [])
    if args.zerar:
        print("(zerando os poderes atuais)")
    ja_tem = {
        (p.get("nome") or "").lower()
        for p in atuais
        if isinstance(p, dict)
    }
    print(f"poderes atuais: {len(atuais)}")

    niveis = niveis_do_catalogo(db)
    print(f"catalogo de poderes: {len(niveis)}")

    # Personagens que tem poderes listados; sao a origem de cada conquista.
    fontes = [
        d.to_dict() or {}
        for d in db.collection("personagens").limit(200).get()
        if (d.to_dict() or {}).get("poderes")
    ]
    if not fontes:
        sys.exit("Nenhum personagem com poderes. Rode: python carregar_poderes.py --com-personagens 25")
    random.shuffle(fontes)
    print(f"personagens disponiveis: {len(fontes)}")
    print()

    # Monta um conjunto variado de proposito: sortear "os mais raros" dava
    # 14 poderes Nv4/Nv5, e pegar em ordem dava tudo da mesma origem. Aqui a
    # distribuicao e por faixa de nivel, uma origem diferente a cada vez.
    candidatos: list[tuple[int, str, str]] = []
    vistos: set[str] = set()
    for personagem in fontes:
        origem = personagem.get("nome", "?")
        for nome_poder in personagem.get("poderes", []):
            baixo = nome_poder.lower()
            if baixo in ja_tem or baixo in vistos:
                continue
            vistos.add(baixo)
            candidatos.append((niveis.get(baixo, 1), nome_poder, origem))

    por_nivel: dict[int, list[tuple[int, str, str]]] = {}
    for item in candidatos:
        por_nivel.setdefault(item[0], []).append(item)
    for lista in por_nivel.values():
        random.shuffle(lista)

    # Proporcao: mais comuns que raros, como num RPG de verdade.
    cota = {1: 0.30, 2: 0.25, 3: 0.20, 4: 0.15, 5: 0.10}
    novos: list[dict[str, Any]] = []
    origens_usadas: set[str] = set()

    for nivel, fracao in sorted(cota.items()):
        alvo = max(1, round(args.quantos * fracao))
        pegos = 0
        for item in list(por_nivel.get(nivel, [])):
            if pegos >= alvo or len(novos) >= args.quantos:
                break
            _, nome_poder, origem = item
            # Evita repetir origem enquanto houver personagem novo disponivel.
            if origem in origens_usadas and len(origens_usadas) < len(fontes):
                continue
            origens_usadas.add(origem)
            por_nivel[nivel].remove(item)
            novos.append({"nome": nome_poder, "nivel": nivel, "origemNome": origem})
            pegos += 1

    # Completa o que faltou, de qualquer nivel.
    sobra = [i for lista in por_nivel.values() for i in lista]
    random.shuffle(sobra)
    for nivel, nome_poder, origem in sobra:
        if len(novos) >= args.quantos:
            break
        novos.append({"nome": nome_poder, "nivel": nivel, "origemNome": origem})

    novos.sort(key=lambda p: (-p["nivel"], p["nome"]))
    for p_ in novos:
        print(f"  + Nv{p_['nivel']}  {p_['nome']:<28} ({p_['origemNome']})")

    if not novos:
        print("Nada novo para conceder.")
        return

    ref.update({"poderes": atuais + novos})
    print()
    print(f"{len(novos)} poderes concedidos. Total agora: {len(atuais) + len(novos)}")


if __name__ == "__main__":
    main()
