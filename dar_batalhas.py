#!/usr/bin/env python3
"""Gera batalhas encerradas para um agente, para o historico nao abrir vazio.

Nao inventa numero: a mecanica aqui e a mesma de
`data/repo/MecanicaBatalha.kt` no app — mesmos HP por ameaca, mesmo ataque
pela soma dos niveis equipados, mesma chance de esquiva, mesmo XP. O que
muda e so quem roda o loop.

As falas saem do narrador de verdade (`agents/battle_narrator.py`), entao o
historico fica igual ao que o app teria gravado jogando.

    python dar_batalhas.py --email alguem@exemplo.com --quantas 2

Usa o Admin SDK, entao nao precisa da senha de ninguem.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from firebase_admin import auth, firestore  # noqa: E402

from agents.battle_narrator import narrar_turno  # noqa: E402
from deps.firebase import get_firestore  # noqa: E402

MAX_PODERES = 3          # MAX_PODERES do LoadoutFragment
RECARGA_ESPECIAL = 3     # MecanicaBatalha.RECARGA_ESPECIAL
LIMITE_TURNOS = 40       # trava de seguranca: luta real termina bem antes


# --------------------------------------------------------------- mecanica
def peso_ameaca(ameaca: str) -> int:
    return {"alta": 14, "media": 10}.get(ameaca, 7)


def hp_do_oponente(ameaca: str) -> int:
    return {"alta": 160, "media": 120}.get(ameaca, 90)


def hp_do_jogador(nivel: int) -> int:
    return 100 + nivel * 5


def ataque_do_jogador(nivel: int, loadout: list[dict]) -> int:
    return 8 + nivel // 2 + sum(p["nivel"] for p in loadout)


def defesa_do_jogador(nivel: int, loadout: list[dict]) -> int:
    return 4 + nivel // 3 + len(loadout) * 2


def esquiva_do_jogador(loadout: list[dict]) -> int:
    return min(sum(p["nivel"] for p in loadout), 30)


def poder_do_turno(acao: str, loadout: list[dict], turno: int) -> str:
    if not loadout:
        return "Ataque basico"
    if acao == "DEFENDER":
        return "Defesa"
    if acao == "ESPECIAL":
        return max(loadout, key=lambda p: p["nivel"])["nome"]
    return loadout[turno % len(loadout)]["nome"]


def resolver_turno(
    acao: str,
    nivel: int,
    loadout: list[dict],
    ameaca: str,
    hp_jogador: int,
    hp_oponente: int,
    turno: int,
    rng: random.Random,
) -> dict[str, Any]:
    """Porte de MecanicaBatalha.resolverTurno, campo por campo."""
    ataque = ataque_do_jogador(nivel, loadout)
    defesa = defesa_do_jogador(nivel, loadout)
    poder = poder_do_turno(acao, loadout, turno)

    multiplicador = {"ATACAR": 1.0, "DEFENDER": 0.45, "ESPECIAL": 1.6}[acao]
    critico = acao != "DEFENDER" and rng.randrange(100) < 15
    variacao = rng.randrange(-2, 3)

    bruto = int(ataque * multiplicador) + variacao
    dano = max(1, int(bruto * 1.5) if critico else bruto)

    oponente_esquivou = rng.randrange(100) < peso_ameaca(ameaca)
    hp_oponente_novo = hp_oponente if oponente_esquivou else max(0, hp_oponente - dano)

    if hp_oponente_novo == 0:
        return {
            "dano": dano, "esquivou": oponente_esquivou, "critico": critico,
            "poder": poder, "dano_recebido": 0, "jogador_esquivou": False,
            "hp_jogador": hp_jogador, "hp_oponente": 0,
            "acabou": True, "venceu": True,
        }

    ataque_inimigo = peso_ameaca(ameaca) + rng.randrange(2, 9)
    mitigado = defesa * 2 if acao == "DEFENDER" else defesa
    dano_recebido = max(1, ataque_inimigo - mitigado // 2)

    jogador_esquivou = rng.randrange(100) < esquiva_do_jogador(loadout)
    hp_jogador_novo = hp_jogador if jogador_esquivou else max(0, hp_jogador - dano_recebido)

    return {
        "dano": dano, "esquivou": oponente_esquivou, "critico": critico,
        "poder": poder, "dano_recebido": 0 if jogador_esquivou else dano_recebido,
        "jogador_esquivou": jogador_esquivou,
        "hp_jogador": hp_jogador_novo, "hp_oponente": hp_oponente_novo,
        "acabou": hp_jogador_novo == 0, "venceu": False,
    }


def xp_da_batalha(venceu: bool, ameaca: str) -> int:
    base = peso_ameaca(ameaca) * 5
    return base if venceu else base // 4


# ----------------------------------------------------------------- escrita
def simular(
    oponente: dict,
    nivel: int,
    loadout: list[dict],
    rng: random.Random,
) -> dict[str, Any]:
    """
    Roda a luta inteira, so com a mecanica.

    Sem narrar: quem chama costuma repetir a simulacao ate sair o resultado
    desejado, e narrar aqui gastaria uma chamada do modelo por tentativa
    jogada fora.
    """
    ameaca = oponente.get("ameaca") or "baixa"
    hp_max_jogador = hp_do_jogador(nivel)
    hp_max_oponente = hp_do_oponente(ameaca)
    hp_jogador, hp_oponente = hp_max_jogador, hp_max_oponente

    turnos: list[dict[str, Any]] = []
    dano_total = 0
    turno = 0
    ultimo_especial = -99
    resultado: dict[str, Any] = {}

    while turno < LIMITE_TURNOS:
        turno += 1
        especial_pronto = turno - ultimo_especial >= RECARGA_ESPECIAL
        # Mistura as acoes como um jogador faria, em vez de martelar ATACAR.
        if especial_pronto and rng.random() < 0.55:
            acao = "ESPECIAL"
            ultimo_especial = turno
        elif rng.random() < 0.2:
            acao = "DEFENDER"
        else:
            acao = "ATACAR"

        resultado = resolver_turno(
            acao, nivel, loadout, ameaca, hp_jogador, hp_oponente, turno, rng
        )
        hp_jogador = resultado["hp_jogador"]
        hp_oponente = resultado["hp_oponente"]
        if not resultado["esquivou"]:
            dano_total += resultado["dano"]

        turnos.append({"acao": acao, "r": resultado})

        if resultado["acabou"]:
            break

    return {
        "venceu": bool(resultado.get("venceu")),
        "turnos": turnos,
        "dano_total": dano_total,
        "hp_jogador": hp_jogador,
        "hp_oponente": hp_oponente,
        "hp_max_jogador": hp_max_jogador,
        "hp_max_oponente": hp_max_oponente,
        "ameaca": ameaca,
    }


def narrar(nome_jogador: str, oponente: dict, luta: dict) -> None:
    """Preenche as falas da luta ja escolhida, um turno por vez."""
    hp_max_j = luta["hp_max_jogador"]
    hp_max_o = luta["hp_max_oponente"]
    for i, t in enumerate(luta["turnos"], start=1):
        r = t["r"]
        t["fala_agente"], t["fala_oponente"] = narrar_turno(
            nome_jogador=nome_jogador,
            nome_oponente=oponente["nome"],
            acao=r["poder"],
            dano=r["dano"],
            esquivou=r["esquivou"],
            critico=r["critico"],
            dano_recebido=r["dano_recebido"],
            jogador_esquivou=r["jogador_esquivou"],
            oponente_caiu=r["hp_oponente"] == 0,
        )
        print(f"    turno {i:>2} [{t['acao']:<8}] -{r['dano']:>3} | "
              f"HP {r['hp_jogador']:>3}/{hp_max_j} vs {r['hp_oponente']:>3}/{hp_max_o}")
        print(f"             {t['fala_agente']}")
        if t["fala_oponente"]:
            print(f"             {t['fala_oponente']}")


def gravar(db, uid: str, oponente: dict, luta: dict, quando: datetime) -> str:
    """Escreve o documento no mesmo formato que o app grava jogando."""
    ref = db.collection("users").document(uid).collection("batalhas").document()

    falas: list[dict[str, Any]] = []
    instante = quando
    for t in luta["turnos"]:
        r = t["r"]
        instante = instante + timedelta(seconds=6)
        falas.append({
            "dano": r["dano"], "esquivou": r["esquivou"], "critico": r["critico"],
            "texto": t["fala_agente"], "doAgente": True, "timestamp": instante,
        })
        if t["fala_oponente"]:
            falas.append({
                "dano": r["dano_recebido"], "esquivou": r["jogador_esquivou"],
                "critico": False, "texto": t["fala_oponente"],
                "doAgente": False, "timestamp": instante,
            })

    ref.set({
        "oponenteNome": oponente["nome"],
        "oponenteImagem": oponente.get("imagem") or "",
        "oponenteAmeaca": luta["ameaca"],
        "hpJogador": luta["hp_jogador"],
        "hpOponente": luta["hp_oponente"],
        "hpMaximoJogador": luta["hp_max_jogador"],
        "hpMaximoOponente": luta["hp_max_oponente"],
        "turnos": falas,
        "status": "vitoria" if luta["venceu"] else "derrota",
        "xpGanho": xp_da_batalha(luta["venceu"], luta["ameaca"]),
        "criadoEm": quando,
        "encerradoEm": instante,
    })
    return ref.id


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--quantas", type=int, default=2)
    p.add_argument("--zerar", action="store_true",
                   help="apaga as batalhas e zera as estatisticas antes")
    args = p.parse_args()

    db = get_firestore()
    rng = random.Random()

    try:
        usuario = auth.get_user_by_email(args.email)
    except Exception as e:
        sys.exit(f"Usuario nao encontrado: {e}")

    uid = usuario.uid
    ref = db.collection("users").document(uid)
    snap = ref.get()
    if not snap.exists:
        sys.exit("Esse uid nao tem ficha em users/. Entre no app uma vez primeiro.")

    perfil = snap.to_dict() or {}
    nivel = int(perfil.get("nivel") or 1)
    poderes = [p for p in (perfil.get("poderes") or []) if isinstance(p, dict)]
    nome_jogador = perfil.get("codinome") or "Agente"
    # O codinome pode ter ficado com o e-mail inteiro; na fala isso fica feio.
    if "@" in nome_jogador:
        nome_jogador = nome_jogador.split("@")[0]

    if not poderes:
        sys.exit("O agente nao tem poderes. Rode dar_poderes.py antes.")

    print(f"agente: {args.email}  (uid {uid})")
    print(f"nivel {nivel} | {len(poderes)} poderes")

    if args.zerar:
        antigas = list(ref.collection("batalhas").limit(100).get())
        for d in antigas:
            d.reference.delete()
        ref.update({
            "estatisticas.vitorias": 0, "estatisticas.derrotas": 0,
            "estatisticas.sequencia": 0, "estatisticas.danoTotal": 0,
        })
        print(f"(apagadas {len(antigas)} batalhas e zeradas as estatisticas)")

    # Loadout: os tres mais fortes, que e o que o jogador equiparia.
    loadout = sorted(poderes, key=lambda x: -int(x.get("nivel") or 1))[:MAX_PODERES]
    print("loadout: " + ", ".join(f"{p['nome']} (Nv{p['nivel']})" for p in loadout))

    oponentes = [
        d.to_dict() | {"id": d.id}
        for d in db.collection("personagens").limit(200).get()
        if (d.to_dict() or {}).get("nome")
    ]
    if not oponentes:
        sys.exit("Nenhum personagem no catalogo.")
    rng.shuffle(oponentes)

    # Uma vitoria e uma derrota: o historico mostra as duas cores e a tela de
    # desempenho sai de 0% ou 100%, que nao diz nada.
    desejados = [True, False] + [None] * max(0, args.quantas - 2)
    desejados = desejados[: args.quantas]

    vitorias = derrotas = dano_total = xp_total = 0
    sequencia = 0
    quando = datetime.now(timezone.utc) - timedelta(hours=len(desejados) * 2)

    for i, quero_vitoria in enumerate(desejados, start=1):
        # Oponente forte para a derrota, mais leve para a vitoria.
        pool = [o for o in oponentes if (o.get("ameaca") == "alta") == (quero_vitoria is False)]
        oponente = (pool or oponentes)[i % len(pool or oponentes)]

        print(f"\n[{i}/{len(desejados)}] {nome_jogador} vs {oponente['nome']} "
              f"(ameaca {oponente.get('ameaca')})")

        # Simula ate sair o resultado pedido; so entao gasta o narrador.
        luta = simular(oponente, nivel, loadout, rng)
        for _ in range(40):
            if quero_vitoria is None or luta["venceu"] == quero_vitoria:
                break
            luta = simular(oponente, nivel, loadout, rng)
        narrar(nome_jogador, oponente, luta)

        quando = quando + timedelta(hours=2)
        battle_id = gravar(db, uid, oponente, luta, quando)
        xp = xp_da_batalha(luta["venceu"], luta["ameaca"])

        if luta["venceu"]:
            vitorias += 1
            sequencia += 1
        else:
            derrotas += 1
            sequencia = 0
        dano_total += luta["dano_total"]
        xp_total += xp

        print(f"    -> {'VITORIA' if luta['venceu'] else 'DERROTA'} em "
              f"{len(luta['turnos'])} turnos, +{xp} XP  (doc {battle_id})")

    # Mesmas somas que BatalhaRepository.encerrar faria, de uma vez so.
    ref.update({
        "xp": firestore.Increment(xp_total),
        "estatisticas.vitorias": firestore.Increment(vitorias),
        "estatisticas.derrotas": firestore.Increment(derrotas),
        "estatisticas.danoTotal": firestore.Increment(dano_total),
        "estatisticas.sequencia": sequencia,
    })

    print(f"\n{len(desejados)} batalhas gravadas: {vitorias}V {derrotas}D")
    print(f"+{xp_total} XP | +{dano_total} de dano total | sequencia {sequencia}")


if __name__ == "__main__":
    main()
