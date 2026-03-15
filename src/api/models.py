"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


# Chat models
class ChatMessageRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]]
    confidence: float
    conversation_id: Optional[str] = None


class ChatSessionCreate(BaseModel):
    title: str


class ChatSessionResponse(BaseModel):
    session_id: int
    title: str
    created_at: datetime
    message_count: int


class ChatMessageResponse(BaseModel):
    message_id: int
    sender: str
    message_text: str
    created_at: datetime
    confidence: Optional[float]


# Search models
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_found: int


class StatsResponse(BaseModel):
    total_documents: int
    total_embeddings: int
    documents_with_embeddings: int
    embedding_coverage: str


# Authentication models
class UserLogin(BaseModel):
    email: str
    password: str


class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    created_at: datetime


class UserPreferencesUpdate(BaseModel):
    region: Optional[str] = None
    focus_topics: Optional[List[str]] = None
    language: Optional[str] = None


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


# Collections models
class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


# Tags models
class TagCreate(BaseModel):
    tag_name: str

