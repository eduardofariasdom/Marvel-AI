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

    # Golpe do agente
    dano: int = 0
    esquivou: bool = False       # o OPONENTE esquivou
    critico: bool = False

    # Revide do oponente
    dano_recebido: int = 0
    jogador_esquivou: bool = False
    oponente_caiu: bool = False


class TurnoResposta(BaseModel):
    """As duas falas do turno. `oponente` vem vazia quando ele caiu."""

    narracao: str
    narracao_oponente: str = ""


@router.post("/narrate", response_model=TurnoResposta)
def narrar(
    body: TurnoRequest,
    uid: str = Depends(verify_firebase_token),
) -> TurnoResposta:
    """
    Narra um turno inteiro: a acao do agente e o revide do oponente.

    Pura narracao — quem calcula o dano e quem grava no Firestore e o app,
    que e dono da partida.
    """
    agente, oponente = narrar_turno(
        nome_jogador=body.nome_jogador,
        nome_oponente=body.nome_oponente,
        acao=body.acao,
        dano=body.dano,
        esquivou=body.esquivou,
        critico=body.critico,
        dano_recebido=body.dano_recebido,
        jogador_esquivou=body.jogador_esquivou,
        oponente_caiu=body.oponente_caiu,
    )
    return TurnoResposta(narracao=agente, narracao_oponente=oponente)
