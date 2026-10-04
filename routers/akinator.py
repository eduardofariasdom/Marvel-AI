"""Router do Akinator: POST /akinator/start e POST /akinator/answer."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore as gcf
from pydantic import BaseModel, Field

from agents.akinator_agent import LIMITE_PERGUNTAS, proxima_jogada
from deps.auth import verify_firebase_token
from deps.firebase import get_firestore

router = APIRouter(prefix="/akinator", tags=["akinator"])


class Jogada(BaseModel):
    """Pergunta ou palpite devolvido ao app."""

    game_id: str
    tipo: Literal["pergunta", "palpite"]
    texto: str
    personagem: str = ""
    personagem_en: str = ""
    rodada: int
    encerrado: bool = False


class RespostaRequest(BaseModel):
    """Resposta do jogador para a pergunta anterior."""

    game_id: str = Field(..., min_length=1)
    resposta: Literal["sim", "nao", "talvez"]


class VeredictoRequest(BaseModel):
    """Confirma ou nega o palpite do Scanner."""

    game_id: str = Field(..., min_length=1)
    acertou: bool


def _doc(uid: str, game_id: str):
    """Referencia de users/{uid}/akinator/{gameId}."""
    return (
        get_firestore()
        .collection("users")
        .document(uid)
        .collection("akinator")
        .document(game_id)
    )


def _carregar(uid: str, game_id: str) -> dict[str, Any]:
    """Le a partida, recusando id inexistente ou ja encerrado."""
    snap = _doc(uid, game_id).get()
    if not snap.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partida nao encontrada.",
        )
    partida: dict[str, Any] = snap.to_dict() or {}
    if partida.get("status") == "encerrado":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta partida ja foi encerrada.",
        )
    return partida


@router.post("/start", response_model=Jogada)
def comecar(uid: str = Depends(verify_firebase_token)) -> Jogada:
    """Abre uma partida nova e devolve a primeira pergunta."""
    jogada = proxima_jogada(historico=[])

    db = get_firestore()
    ref = db.collection("users").document(uid).collection("akinator").document()
    ref.set(
        {
            "status": "em_andamento",
            "historico": [],
            "perguntaAtual": jogada["texto"],
            "criadoEm": gcf.SERVER_TIMESTAMP,
        }
    )

    return Jogada(
        game_id=ref.id,
        tipo=jogada["tipo"],
        texto=jogada["texto"],
        personagem=jogada["personagem"],
        personagem_en=jogada.get("personagem_en", ""),
        rodada=1,
    )


@router.post("/answer", response_model=Jogada)
def responder(
    body: RespostaRequest,
    uid: str = Depends(verify_firebase_token),
) -> Jogada:
    """Registra a resposta e devolve a proxima pergunta ou o palpite."""
    partida = _carregar(uid, body.game_id)

    historico: list[dict[str, str]] = list(partida.get("historico") or [])
    historico.append(
        {
            "pergunta": partida.get("perguntaAtual", ""),
            "resposta": body.resposta,
        }
    )

    jogada = proxima_jogada(historico)
    e_palpite = jogada["tipo"] == "palpite"

    _doc(uid, body.game_id).update(
        {
            "historico": historico,
            "perguntaAtual": jogada["texto"],
            "palpite": jogada["personagem"] if e_palpite else "",
            # Guardado para o /finish devolver o mesmo nome de busca.
            "palpite_en": jogada.get("personagem_en", "") if e_palpite else "",
        }
    )

    return Jogada(
        game_id=body.game_id,
        tipo=jogada["tipo"],
        texto=jogada["texto"],
        personagem=jogada["personagem"],
        personagem_en=jogada.get("personagem_en", ""),
        rodada=len(historico) + 1,
        encerrado=len(historico) >= LIMITE_PERGUNTAS,
    )


@router.post("/finish", response_model=Jogada)
def encerrar(
    body: VeredictoRequest,
    uid: str = Depends(verify_firebase_token),
) -> Jogada:
    """Fecha a partida depois do palpite, guardando se o Scanner acertou."""
    partida = _carregar(uid, body.game_id)
    historico: list[dict[str, str]] = list(partida.get("historico") or [])

    _doc(uid, body.game_id).update(
        {
            "status": "encerrado",
            "acertou": body.acertou,
            "encerradoEm": gcf.SERVER_TIMESTAMP,
        }
    )

    texto = (
        "O Scanner nunca falha, agente."
        if body.acertou
        else "Dessa vez voce escapou do radar. Vamos de novo?"
    )
    return Jogada(
        game_id=body.game_id,
        tipo="palpite",
        texto=texto,
        personagem=partida.get("palpite", ""),
        personagem_en=partida.get("palpite_en", ""),
        rodada=len(historico),
        encerrado=True,
    )
