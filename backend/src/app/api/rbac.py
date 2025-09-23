from functools import wraps
from fastapi import HTTPException, Depends
from app.services.auth import get_current_user

def require_role(required_role: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Assume get_current_user is implemented
            user = kwargs.get('current_user')  # placeholder
            if not user or user.get('role') != required_role:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator