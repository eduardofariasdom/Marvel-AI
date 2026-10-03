"""Router do Jarvis: POST /jarvis/query."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore as gcf
from pydantic import BaseModel, Field

from agents.jarvis_agent import invocar_jarvis
from deps.auth import verify_firebase_token
from deps.firebase import get_firestore
from tools.firestore_tools import uid_atual

router = APIRouter(prefix="/jarvis", tags=["jarvis"])


class JarvisQuery(BaseModel):
    """Pergunta enviada pelo jogador."""

    texto: str = Field(..., min_length=1, max_length=1000)


class JarvisResposta(BaseModel):
    """Resposta gerada pelo agente."""

    resposta: str


def _formatar_perfil(perfil: dict[str, Any]) -> str:
    """Transforma o documento users/{uid} em texto simples para o agente ler."""
    codinome: str = perfil.get("codinome") or "Agente"
    nivel: Any = perfil.get("nivel", 1)
    xp: Any = perfil.get("xp", 0)

    poderes_raw = perfil.get("poderes") or []
    if poderes_raw:
        poderes = "; ".join(
            f"{p.get('nome', '?')} (nivel {p.get('nivel', '?')}, origem: {p.get('origemNome', '?')})"
            for p in poderes_raw
            if isinstance(p, dict)
        )
    else:
        poderes = "nenhum poder registrado"

    estatisticas_raw = perfil.get("estatisticas") or {}
    if isinstance(estatisticas_raw, dict) and estatisticas_raw:
        estatisticas = ", ".join(f"{k}: {v}" for k, v in estatisticas_raw.items())
    else:
        estatisticas = "sem estatisticas registradas"

    return (
        "DADOS DO AGENTE (use apenas estes valores):\n"
        f"- Codinome: {codinome}\n"
        f"- Nivel: {nivel}\n"
        f"- XP: {xp}\n"
        f"- Poderes: {poderes}\n"
        f"- Estatisticas: {estatisticas}\n"
    )


@router.post("/query", response_model=JarvisResposta)
def consultar_jarvis(
    body: JarvisQuery,
    uid: str = Depends(verify_firebase_token),
) -> JarvisResposta:
    """Responde a pergunta do jogador com o contexto do perfil dele no Firestore."""
    db = get_firestore()
    snapshot = db.collection("users").document(uid).get()
    perfil: dict[str, Any] = snapshot.to_dict() or {} if snapshot.exists else {}

    pergunta_com_contexto: str = (
        f"{_formatar_perfil(perfil)}\nPERGUNTA DO AGENTE: {body.texto}"
    )

    # As tools de Firestore leem o uid daqui; o modelo nunca o escolhe.
    marcador = uid_atual.set(uid)
    try:
        resposta: str = invocar_jarvis(pergunta_com_contexto)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Jarvis esta fora do ar no momento.",
        ) from exc
    finally:
        uid_atual.reset(marcador)

    try:
        db.collection("users").document(uid).collection("jarvisLogs").add(
            {
                "pergunta": body.texto,
                "resposta": resposta,
                "timestamp": gcf.SERVER_TIMESTAMP,
            }
        )
    except Exception:
        # O log e opcional: nunca deve derrubar a resposta.
        pass

    return JarvisResposta(resposta=resposta)
