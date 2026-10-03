"""Dependency do FastAPI para validar o ID token do Firebase."""

from fastapi import Header, HTTPException, status
from firebase_admin import auth as firebase_auth

from deps.firebase import get_firestore


def verify_firebase_token(authorization: str = Header(...)) -> str:
    """Extrai o Bearer token do header Authorization e retorna o uid do usuario."""
    # Garante que o firebase_admin ja foi inicializado antes de verificar o token.
    get_firestore()

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization ausente ou fora do formato 'Bearer <token>'.",
        )

    token: str = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token vazio.",
        )

    try:
        decoded: dict = firebase_auth.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado.",
        ) from exc

    uid: str | None = decoded.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem uid.",
        )
    return uid
