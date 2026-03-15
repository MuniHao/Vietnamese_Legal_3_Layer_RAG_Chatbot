"""
FastAPI backend for Law Chat application
"""
from fastapi import FastAPI, Depends, HTTPException, Query, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import asyncio
import time

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from models.database import (
    get_db, test_connection, User, ChatSession, ChatMessage, UserPreference, MessageSender,
    SavedDocument, Collection, CollectionDocument, DocumentTag, Document
)
from services.rag_service import rag_service
from services.auth_service import auth_service
from api.auth_dependencies import get_current_user, get_current_user_optional, require_admin
from utils.text_processor import get_text_processor
from utils.citation_manager import get_citation_manager
from utils.conversation_mapper import get_session_id_from_conversation_id, get_conversation_id_from_session_id
from utils.query_enhancer import enhance_query

# Load environment variables
config_path = Path(__file__).parent.parent.parent / 'config.env'
load_dotenv(config_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Debug flag (controls verbose error messages)
DEBUG = os.getenv("DEBUG", "False").lower() in {"1", "true", "yes", "y"}

# Create FastAPI app
app = FastAPI(
    title="Law Chat Assistant API",
    description="AI-powered legal document search and consultation system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    logger.error(f"Request path: {request.url.path}")
    logger.error(f"Request query params: {request.url.query}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Import Pydantic models from separate file
from api.models import (
    ChatMessageRequest, ChatResponse, ChatSessionCreate, ChatSessionResponse,
    ChatMessageResponse, SearchRequest, SearchResponse,
    StatsResponse, UserLogin, UserRegister, Token, UserResponse,
    UserPreferencesUpdate, UserProfileUpdate
)

# Initialize text processor (singleton)
text_processor = get_text_processor()

# Preload embedding model on startup
@app.on_event("startup")
async def startup_event():
    """Preload embedding model when app starts"""
    try:
        logger.info("=" * 80)
        logger.info("Starting Law Chat Assistant API...")
        
        # Preload embedding model
        logger.info("Preloading embedding model: BAAI/bge-m3...")
        start_time = time.time()
        model = rag_service.load_embedding_model()
        load_time = time.time() - start_time
        logger.info(f"Embedding model loaded successfully in {load_time:.2f}s")
        
        # Warmup encode function to avoid first-request delay (19s → 0.9s)
        logger.info("Warming up embedding encode function...")
        warmup_start = time.time()
        try:
            # Test encode with the short question to warmup Metal/GPU backend
            test_query = "test query to warmup model"
            if 'bge-m3' in os.getenv('EMBEDDING_MODEL', '').lower():
                test_query_with_prefix = f"You are finding: {test_query}"
                _ = model.encode(test_query_with_prefix, normalize_embeddings=True)
            else:
                _ = model.encode(test_query)
            warmup_time = time.time() - warmup_start
            logger.info(f"Embedding encode warmed up in {warmup_time:.2f}s (first request will be fast now)")
        except Exception as e:
            logger.warning(f"Warmup failed (non-critical): {e}")
        
        # Preload reranker model if enabled
        if rag_service.use_reranker:
            logger.info("📦 Preloading reranker model...")
            start_time = time.time()
            reranker = rag_service.load_reranker_model()
            if reranker:
                load_time = time.time() - start_time
                logger.info(f"Reranker model loaded successfully in {load_time:.2f}s")
            else:
                logger.warning("Reranker model not available")
        else:
            logger.info("ℹReranker is disabled, skipping...")
        
        logger.info("API startup completed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Don't raise - let app start anyway, model will load on first request

# Import helper functions
from api.helpers import (
    process_conversation_services,
    _filter_relevant_documents,
    _format_sources_section,
    _generate_fallback_answer
)

# Include routers
from api.routers import auth, chat, chat_history, search, admin, topics, documents, collections, tags

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(chat_history.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(topics.router)
app.include_router(documents.router)
app.include_router(collections.router)
app.include_router(tags.router)

# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Law Chat Assistant API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        if not test_connection():
            raise HTTPException(status_code=503, detail="Database connection failed")
        
        # Get basic stats
        stats = rag_service.get_stats(db)
        
        return {
            "status": "healthy",
            "database": "connected",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting Law Chat API server on {host}:{port}")
    # Run app directly instead of using string path
    # Note: reload doesn't work well with app object, so disable it
    uvicorn.run(
        app,  # Run app object directly
        host=host,
        port=port,
        reload=False,  # Disable reload when using app object
        log_level="info"
    )
