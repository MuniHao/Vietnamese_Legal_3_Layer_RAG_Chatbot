"""
Authentication and user management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import timedelta

from models.database import get_db, User
from api.auth_dependencies import get_current_user
from services.auth_service import auth_service
from api.models import UserLogin, UserRegister, UserResponse, Token, UserPreferencesUpdate, UserProfileUpdate

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    try:
        # Normalize email
        normalized_email = (user_data.email or "").strip().lower()

        user = auth_service.create_user(
            db=db,
            email=normalized_email,
            password=user_data.password,
            full_name=user_data.full_name,
            phone=user_data.phone
        )
        
        if not user:
            # Distinguish duplicate email vs other errors
            exists = auth_service.get_user_by_email(db, normalized_email)
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Registration failed"
                )
        
        return UserResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            role=user.role.value,
            created_at=user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Registration error: {e}")
        import os
        DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes", "y"}
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=Token)
async def login_user(
    user_credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """Login user and return JWT token"""
    try:
        user = auth_service.authenticate_user(
            db=db,
            email=user_credentials.email,
            password=user_credentials.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=auth_service.access_token_expire_minutes)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.user_id)},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth_service.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        role=current_user.role.value,
        created_at=current_user.created_at
    )


@router.put("/preferences")
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user preferences"""
    try:
        success = auth_service.update_user_preferences(
            db=db,
            user_id=current_user.user_id,
            region=preferences.region,
            focus_topics=preferences.focus_topics,
            language=preferences.language
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update preferences")
        
        return {"message": "Preferences updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Preferences update error: {e}")
        raise HTTPException(status_code=500, detail="Preferences update failed")


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    profile: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile (full_name, phone)"""
    try:
        updated_user = auth_service.update_user_profile(
            db=db,
            user_id=current_user.user_id,
            full_name=profile.full_name,
            phone=profile.phone
        )
        
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to update profile")
        
        return UserResponse(
            user_id=updated_user.user_id,
            email=updated_user.email,
            full_name=updated_user.full_name,
            phone=updated_user.phone,
            role=updated_user.role.value,
            created_at=updated_user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")

