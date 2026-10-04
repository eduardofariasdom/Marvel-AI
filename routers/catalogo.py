"""Router do catalogo: o app busca personagens e times por aqui.

Passa pelo servidor para a chave da ComicVine nao precisar ir dentro do APK.
O resultado ja vem mesclado com o Firestore e cacheado la.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from deps.auth import verify_firebase_token
from tools import catalogo_servico, comicvine

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


class PersonagemResposta(BaseModel):
    """Personagem no formato que o app espera."""

    nome: str = ""
    alterEgo: str = ""
    heroi: bool = True
    ameaca: str = ""
    poderes: list[str] = []
    times: list[str] = []
    deck: str = ""
    imagem: str = ""
    fonte: str = "firestore"


class TimeResposta(BaseModel):
    """Time no formato que o app espera."""

    nome: str = ""
    membros: list[str] = []
    deck: str = ""
    imagem: str = ""
    fonte: str = "firestore"


@router.get("/personagens", response_model=list[PersonagemResposta])
def personagens(
    busca: str = Query("", max_length=80),
    limite: int = Query(10, ge=1, le=30),
    uid: str = Depends(verify_firebase_token),
) -> list[PersonagemResposta]:
    """Busca personagens na ComicVine, caindo no Firestore se ela falhar."""
    achados = catalogo_servico.buscar_personagens(busca, limite)
    return [PersonagemResposta(**{k: v for k, v in p.items() if k in PersonagemResposta.model_fields}) for p in achados]


@router.get("/times", response_model=list[TimeResposta])
def times(
    busca: str = Query("", max_length=80),
    limite: int = Query(10, ge=1, le=30),
    uid: str = Depends(verify_firebase_token),
) -> list[TimeResposta]:
    """Busca times na ComicVine, caindo no Firestore se ela falhar."""
    achados = catalogo_servico.buscar_times(busca, limite)
    return [TimeResposta(**{k: v for k, v in t.items() if k in TimeResposta.model_fields}) for t in achados]


@router.get("/status")
def status(uid: str = Depends(verify_firebase_token)) -> dict[str, bool]:
    """Diz se a ComicVine esta configurada, util para depurar o app."""
    return {"comicvine": comicvine.disponivel()}
