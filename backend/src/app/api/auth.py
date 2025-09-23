from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.services import auth as auth_service
from app.db.deps import get_db
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    acceptTerms: bool


@router.post("/login")
def login(req: LoginRequest):
    result = auth_service.authenticate(str(req.email), req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, user = result
    return {"token": token, "user": user}


@router.post("/logout", status_code=204)
def logout():
    # MVP: stateless logout (client clears token)
    return None


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if not req.acceptTerms:
        raise HTTPException(status_code=400, detail="Terms must be accepted")
    try:
        user = auth_service.register(db, name=req.name, email=str(req.email), password=req.password)
    except auth_service.EmailAlreadyExistsError:
        # Idempotent behavior: if the user already exists and the password matches, treat as login
        auth = auth_service.authenticate(str(req.email), req.password)
        if not auth:
            raise HTTPException(status_code=400, detail="Email already registered")
        token, auth_user = auth
        return JSONResponse(status_code=200, content={"token": token, "user": auth_user})
    # Optionally auto-login and return a token
    token, _ = auth_service.authenticate(user.email, req.password) or (None, None)
    body: dict[str, object] = {"user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}}
    if token:
        body["token"] = token
    return body
