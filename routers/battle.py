"""Router da narracao de batalha: POST /battle/narrate."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agents.battle_narrator import narrar_turno
from deps.auth import verify_firebase_token

router = APIRouter(prefix="/battle", tags=["battle"])


class TurnoRequest(BaseModel):
    """Numeros ja calculados pelo app para este turno."""

    battle_id: str = Field(..., min_length=1)
    nome_jogador: str = Field(..., min_length=1)
    nome_oponente: str = Field(..., min_length=1)
    acao: str = Field(..., min_length=1)
    dano: int
    esquivou: bool
    critico: bool = False


class TurnoResposta(BaseModel):
    """Frase narrada para o turno."""

    narracao: str


@router.post("/narrate", response_model=TurnoResposta)
def narrar(
    body: TurnoRequest,
    uid: str = Depends(verify_firebase_token),
) -> TurnoResposta:
    """
    Narra um turno de batalha.

    Pura narracao: quem calcula o dano e quem grava o turno no Firestore e o
    app, que e dono da partida. Aqui so entra o texto.
    """
    entrada = (
        f"{body.nome_jogador} usa {body.acao} contra {body.nome_oponente}. "
        f"Dano: {body.dano}. Esquiva: {'sim' if body.esquivou else 'nao'}."
    )
    if body.critico:
        entrada += " Foi um acerto critico."

    try:
        narracao = narrar_turno(entrada).strip()
    except Exception:
        narracao = ""

    # A batalha nunca pode travar por uma falha externa de IA.
    if not narracao:
        narracao = f"{body.nome_jogador} ataca {body.nome_oponente}! -{body.dano} HP"

    return TurnoResposta(narracao=narracao)
