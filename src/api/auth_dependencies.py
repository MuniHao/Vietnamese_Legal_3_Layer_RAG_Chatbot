"""
Authentication dependencies for FastAPI
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import logging

from models.database import get_db, User
from services.auth_service import auth_service

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify token
        payload = auth_service.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        # Get user ID from token
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        user = auth_service.get_user_by_id(db, user_id)
        if user is None:
            raise credentials_exception
        
        return user
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
