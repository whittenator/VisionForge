from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.services import auth as auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
