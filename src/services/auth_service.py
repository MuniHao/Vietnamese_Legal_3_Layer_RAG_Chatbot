"""
Authentication service for Law Chat application
"""
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv

# Fix bcrypt compatibility with passlib
# Passlib tries to access bcrypt.__about__.__version__ which doesn't exist in newer bcrypt versions
try:
    import bcrypt
    if not hasattr(bcrypt, '__about__'):
        # Create a compatibility shim for passlib
        class AboutModule:
            __version__ = getattr(bcrypt, '__version__', '4.1.2')
        bcrypt.__about__ = AboutModule()
except ImportError:
    pass

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Add src directory to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from models.database import User, UserRole

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))

# Password hashing
# Use bcrypt_sha256 to safely support passwords > 72 bytes
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

class AuthService:
    """Authentication service for user management and JWT tokens"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password using bcrypt_sha256 (handles long passwords)"""
        try:
            return pwd_context.hash(password)
        except ValueError as e:
            # Handle case where password might be too long during passlib's internal checks
            # bcrypt_sha256 should handle long passwords, but passlib has a bug in its detection logic
            logger.error(f"Password hashing error: {e}")
            # Re-raise with a more user-friendly message
            raise ValueError("Password processing failed. Please try again or contact support.")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            return None
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password"""
        normalized_email = (email or "").strip().lower()
        user = db.query(User).filter(User.email == normalized_email).first()
        
        if not user:
            logger.warning(f"User not found: {email}")
            return None
        
        if not self.verify_password(password, user.password_hash):
            logger.warning(f"Invalid password for user: {email}")
            return None
        
        logger.info(f"User authenticated successfully: {email}")
        return user
    
    def create_user(self, db: Session, email: str, password: str, full_name: str, phone: str = None) -> Optional[User]:
        """Create a new user"""
        # Normalize email (trim + lowercase)
        normalized_email = (email or "").strip().lower()

        # Check if user already exists (case-insensitive via normalized storage)
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            logger.warning(f"User already exists: {normalized_email}")
            return None
        
        # Create new user
        hashed_password = self.get_password_hash(password)
        
        # Let database default handle role ('user') to avoid enum mismatch
        user = User(
            email=normalized_email,
            password_hash=hashed_password,
            full_name=full_name,
            phone=phone,
        )
        
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User created successfully: {email}")
            return user
        except IntegrityError as e:
            # Handle race condition: unique violation on email
            logger.warning(f"Integrity error creating user (likely duplicate email): {e}")
            db.rollback()
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            db.rollback()
            return None
    
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.user_id == user_id).first()
    
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    def update_user_preferences(self, db: Session, user_id: int, region: str = None, 
                               focus_topics: list = None, language: str = None) -> bool:
        """Update user preferences"""
        from models.database import UserPreference
        
        try:
            # Get or create user preferences
            preferences = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            
            if not preferences:
                preferences = UserPreference(user_id=user_id)
                db.add(preferences)
            
            # Update fields
            if region is not None:
                preferences.region = region
            if focus_topics is not None:
                preferences.focus_topics = focus_topics
            if language is not None:
                preferences.language = language
            
            preferences.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"User preferences updated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            db.rollback()
            return False
    
    def update_user_profile(self, db: Session, user_id: int, full_name: str = None, 
                           phone: str = None) -> Optional[User]:
        """Update user profile (full_name, phone)"""
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                logger.warning(f"User not found: {user_id}")
                return None
            
            # Update fields
            if full_name is not None:
                user.full_name = full_name
            if phone is not None:
                user.phone = phone
            
            db.commit()
            db.refresh(user)
            logger.info(f"User profile updated for user {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            db.rollback()
            return None

# Global auth service instance
auth_service = AuthService()

