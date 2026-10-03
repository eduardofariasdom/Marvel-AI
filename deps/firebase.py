"""Inicializacao singleton do firebase-admin e acesso ao Firestore.

A service account pode chegar de duas formas, nesta ordem:

1. FIREBASE_SERVICE_ACCOUNT_FILE - caminho de um arquivo .json.
   E o jeito recomendado no Render: Settings > Secret Files, nome
   `serviceAccount.json`, que o Render monta em /etc/secrets/.
2. FIREBASE_SERVICE_ACCOUNT_JSON - o JSON inteiro numa string, em uma linha.

Nenhuma das duas e o google-services.json do app Android: aquele e
configuracao de cliente e nao tem chave privada.
"""

import json
import os
from pathlib import Path
from typing import Any

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

load_dotenv()

_db: Any = None

# Campos sem os quais o Admin SDK nao consegue assinar um token.
OBRIGATORIOS: tuple[str, ...] = (
    "type",
    "project_id",
    "private_key",
    "client_email",
    "token_uri",
)


def _carregar_service_account() -> dict[str, Any]:
    """Le a service account do arquivo ou da variavel, e valida o formato."""
    caminho = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()
    bruto = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

    if caminho:
        arquivo = Path(caminho)
        if not arquivo.is_file():
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_FILE aponta para '{caminho}', "
                "que nao existe. No Render o Secret File fica em /etc/secrets/."
            )
        bruto = arquivo.read_text(encoding="utf-8")
        origem = f"arquivo {caminho}"
    elif bruto:
        origem = "variavel FIREBASE_SERVICE_ACCOUNT_JSON"
    else:
        raise RuntimeError(
            "Nenhuma credencial do Firebase definida. Use "
            "FIREBASE_SERVICE_ACCOUNT_FILE (caminho do .json) ou "
            "FIREBASE_SERVICE_ACCOUNT_JSON (o JSON numa linha so). "
            "Gere o arquivo em: Firebase Console > Configuracoes do projeto "
            "> Contas de servico > Gerar nova chave privada."
        )

    try:
        dados: dict[str, Any] = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"A credencial vinda da {origem} nao e um JSON valido. "
            "Se colou numa variavel de ambiente, ela precisa estar em uma "
            "linha unica."
        ) from exc

    faltando = [c for c in OBRIGATORIOS if not dados.get(c)]
    if faltando:
        raise RuntimeError(
            f"A credencial vinda da {origem} esta incompleta: faltam "
            f"{', '.join(faltando)}. Isso costuma ser o placeholder do "
            ".env.example, ou o google-services.json do app (que nao serve: "
            "e config de cliente, sem chave privada)."
        )

    # Colada numa variavel de ambiente, a chave privada chega com \\n literal
    # no lugar das quebras de linha. O PEM so e aceito com quebras de verdade.
    chave = dados["private_key"]
    if "\\n" in chave:
        dados["private_key"] = chave.replace("\\n", "\n")

    return dados


def _init_app() -> None:
    """Inicializa o firebase_admin uma unica vez."""
    if firebase_admin._apps:
        return
    firebase_admin.initialize_app(credentials.Certificate(_carregar_service_account()))


def get_firestore() -> Any:
    """Retorna o cliente Firestore, inicializando o app na primeira chamada."""
    global _db
    if _db is None:
        _init_app()
        _db = firestore.client()
    return _db
