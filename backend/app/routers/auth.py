from fastapi import APIRouter, HTTPException

from app.models.schemas import AuthRequest, AuthResponse, RegisterRequest, UserPublic
from app.services.auth_service import authenticate_user, get_current_user, register_user
from fastapi import Depends

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest):
    try:
        token, user = register_user(request.username, request.password)
        return AuthResponse(token=token, user=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthResponse)
def login(request: AuthRequest):
    token, user = authenticate_user(request.username, request.password)
    return AuthResponse(token=token, user=user)


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(get_current_user)):
    return user
