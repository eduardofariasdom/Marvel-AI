#!/usr/bin/env python
"""
Publica o firestore.rules do app sem abrir o Console.

Existe porque as regras ficam no repositorio do mobile mas quem tem
credencial de administrador e este servico. Faz o mesmo que o botao
"Publicar" do Console: cria um ruleset e aponta o release
`cloud.firestore` para ele.

Uso:
    python publicar_regras.py                      # caminho padrao do app
    python publicar_regras.py caminho/para/regras   # outro arquivo
    python publicar_regras.py --mostrar             # so le o que esta no ar

O ruleset antigo continua existindo, entao da para voltar atras pelo
Console (Firestore > Regras > historico).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import google.auth.transport.requests
from dotenv import load_dotenv
from google.oauth2 import service_account

load_dotenv()

API = "https://firebaserules.googleapis.com/v1"
ESCOPO = ["https://www.googleapis.com/auth/firebase"]

# Caminho padrao: o .rules mora no projeto Android, nao aqui.
REGRAS_PADRAO = Path(
    r"C:\Users\eduardodomingues-ieg\AndroidStudioProjects\App-Mobile\firestore.rules"
)


def _credencial() -> service_account.Credentials:
    """Le a service account do mesmo lugar que o resto do servico."""
    import os

    caminho = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
    if caminho and Path(caminho).is_file():
        return service_account.Credentials.from_service_account_file(
            caminho, scopes=ESCOPO
        )

    bruto = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if bruto:
        dados = json.loads(bruto)
        # O .env de uma linha costuma trazer o \n da chave escapado.
        if "private_key" in dados:
            dados["private_key"] = dados["private_key"].replace("\\n", "\n")
        return service_account.Credentials.from_service_account_info(
            dados, scopes=ESCOPO
        )

    sys.exit(
        "Defina FIREBASE_SERVICE_ACCOUNT_FILE (ou _JSON) no .env antes de publicar."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica as regras do Firestore.")
    parser.add_argument(
        "arquivo",
        nargs="?",
        default=str(REGRAS_PADRAO),
        help="caminho do .rules (padrao: o do projeto Android)",
    )
    parser.add_argument(
        "--mostrar",
        action="store_true",
        help="apenas mostra as regras que estao publicadas agora",
    )
    args = parser.parse_args()

    cred = _credencial()
    projeto = cred.project_id
    sessao = google.auth.transport.requests.AuthorizedSession(cred)
    release = f"projects/{projeto}/releases/cloud.firestore"

    if args.mostrar:
        atual = sessao.get(f"{API}/{release}")
        atual.raise_for_status()
        nome = atual.json()["rulesetName"]
        corpo = sessao.get(f"{API}/{nome}")
        corpo.raise_for_status()
        for arq in corpo.json()["source"]["files"]:
            print(f"--- {nome} / {arq['name']} ---")
            print(arq["content"])
        return

    caminho = Path(args.arquivo)
    if not caminho.is_file():
        sys.exit(f"Nao achei o arquivo de regras: {caminho}")
    fonte = caminho.read_text(encoding="utf-8")

    criado = sessao.post(
        f"{API}/projects/{projeto}/rulesets",
        json={"source": {"files": [{"name": "firestore.rules", "content": fonte}]}},
    )
    if criado.status_code >= 400:
        # O erro de sintaxe vem aqui, com linha e coluna: vale mostrar inteiro.
        sys.exit(f"Firebase recusou as regras ({criado.status_code}):\n{criado.text}")
    ruleset = criado.json()["name"]
    print(f"Ruleset criado: {ruleset}")

    publicado = sessao.patch(
        f"{API}/{release}",
        json={"release": {"name": release, "rulesetName": ruleset}},
    )
    if publicado.status_code >= 400:
        sys.exit(f"Falhou ao publicar ({publicado.status_code}):\n{publicado.text}")

    print(f"Publicado em {projeto}: {caminho.name} -> cloud.firestore")


if __name__ == "__main__":
    main()
