"""
Database models and connection setup for Law Chat application
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, JSON, text, ForeignKey, Enum, SmallInteger, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime
import os
from dotenv import load_dotenv
import enum
from zoneinfo import ZoneInfo

# Timezone for Vietnam (HCM +7)
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def get_vietnam_now():
    """The current time is set to Vietnam time zone (+7)"""
    return datetime.now(VIETNAM_TZ).replace(tzinfo=None) 

# Load environment variables
load_dotenv('config.env')

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://nhathao@localhost:5432/phapdien_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Enums
class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class MessageSender(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"

class Document(Base):
    """Document model for legal documents"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    item_guid = Column(UUID(as_uuid=True))
    title = Column(Text, nullable=False)
    doc_number = Column(String)
    issuing_agency = Column(String)
    doc_type = Column(String)
    signing_date = Column(DateTime)
    effective_date = Column(DateTime)
    expiry_date = Column(DateTime)
    status = Column(String)
    summary = Column(Text)
    html_content = Column(Text)
    text_content = Column(Text)
    source_url = Column(String)
    file_url = Column(String)
    checksum = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_crawled_at = Column(DateTime)
    content_tsv = Column(Text)  # Full-text search vector

class Embedding(Base):
    """Embedding model for vector search (legacy - kept for backward compatibility)"""
    __tablename__ = "embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)

    embedding = Column(Vector(1024))  # Updated for BAAI/bge-m3 (1024 dimensions)
    metadata_json = Column('metadata', JSON)
    title = Column(String)
    doc_type = Column(String)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmbeddingDocument(Base):
    """Embedding model for documents (Layer 1 - RAG 3 layer)"""
    __tablename__ = "embedding_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024))  # Updated for BAAI/bge-m3 (1024 dimensions)
    metadata_json = Column('metadata', JSON)
    title = Column(String)
    doc_type = Column(String)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmbeddingCategory(Base):
    """Embedding model for categories (Layer 2 - RAG 3 layer)"""
    __tablename__ = "embedding_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String, unique=True, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024))  # Updated for BAAI/bge-m3 (1024 dimensions)
    metadata_json = Column('metadata', JSON)
    title = Column(String)
    doc_type = Column(String)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Category(Base):
    """Category model for document categorization"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer)
    item_guid = Column(UUID(as_uuid=True))
    title = Column(Text, nullable=False)
    short_title = Column(String)
    description = Column(Text)
    status = Column(String)
    assigned_agency = Column(String)
    source_url = Column(String)
    html_content = Column(Text)  # HTML content from demuc files (with HTML tags)
    content = Column(Text)  # Plain text content from demuc files (no HTML tags)
    created_at = Column(DateTime, default=datetime.utcnow)

class DocumentCategoryMap(Base):
    """Association table for many-to-many relationship between documents and categories"""
    __tablename__ = "document_category_map"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    node_id = Column(Integer)
    notes = Column(Text)

class Topic(Base):
    """Topic model for legal topics"""
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True, index=True)
    item_guid = Column(UUID(as_uuid=True))
    code = Column(String)
    title = Column(Text, nullable=False)
    description = Column(Text)
    ordering = Column(Integer)
    source_id = Column(Integer)
    source_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    """User model for authentication and user management"""
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    phone = Column(String(15))
    # Store enum values ("user"/"admin") in DB and let Postgres default apply
    role = Column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        server_default=text("'user'::user_role")
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")

class ChatSession(Base):
    """Chat session model for grouping messages"""
    __tablename__ = "chat_sessions"
    
    session_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=get_vietnam_now)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """Chat message model for storing conversation history"""
    __tablename__ = "chat_messages"
    
    message_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    # Use Enum with name parameter to match existing PostgreSQL enum type
    sender = Column(
        Enum(
            MessageSender,
            name="message_sender",
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
        nullable=False
    )
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=get_vietnam_now)
    related_doc_id = Column(Integer, ForeignKey("documents.id"))
    confidence = Column(Float)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    related_document = relationship("Document")

class UserPreference(Base):
    """User preference model for personalization"""
    __tablename__ = "user_preferences"
    
    preference_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    region = Column(String(100))
    focus_topics = Column(ARRAY(String))
    language = Column(String(10), default='vi')
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="preferences")

class ConversationSummary(Base):
    """Summary-based memory for conversations"""
    __tablename__ = "conversation_summaries"
    
    summary_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    summary_text = Column(Text, nullable=False)
    message_count = Column(Integer, default=0)  # Số messages đã được summarize
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", backref="summary")

class ConversationTopic(Base):
    """Topic history tracking for conversations"""
    __tablename__ = "conversation_topics"
    
    topic_id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False)
    topic_name = Column(String(255), nullable=False)  # topic name (e.g.  "tranh chấp đất đai")
    topic_keywords = Column(ARRAY(String))  # Some related keyword
    first_mentioned = Column(DateTime, default=datetime.utcnow)
    last_mentioned = Column(DateTime, default=datetime.utcnow)
    mention_count = Column(Integer, default=1)  # Number of times the topic was mentioned
    
    # Relationships
    session = relationship("ChatSession", backref="topics")

class SavedDocument(Base):
    """Saved documents model - user's favorite documents"""
    __tablename__ = "saved_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=get_vietnam_now)
    
    # Relationships
    user = relationship("User", backref="saved_documents")
    document = relationship("Document", backref="saved_by_users")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'document_id', name='unique_user_document'),
    )

class Collection(Base):
    """Collection model - user's document collections/folders"""
    __tablename__ = "collections"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(7))  # Hex color code for UI (e.g., "#FF5733")
    created_at = Column(DateTime, default=get_vietnam_now)
    updated_at = Column(DateTime, default=get_vietnam_now, onupdate=get_vietnam_now)
    
    # Relationships
    user = relationship("User", backref="collections")
    documents = relationship("CollectionDocument", back_populates="collection", cascade="all, delete-orphan")

class CollectionDocument(Base):
    """Association table for documents in collections"""
    __tablename__ = "collection_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime, default=get_vietnam_now)
    notes = Column(Text)  # User notes about this document in collection
    
    # Relationships
    collection = relationship("Collection", back_populates="documents")
    document = relationship("Document", backref="in_collections")
    
    __table_args__ = (
        UniqueConstraint('collection_id', 'document_id', name='unique_collection_document'),
    )

class DocumentTag(Base):
    """Document tags model - user tags for documents"""
    __tablename__ = "document_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=get_vietnam_now)
    
    # Relationships
    user = relationship("User", backref="document_tags")
    document = relationship("Document", backref="tags")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'document_id', 'tag_name', name='unique_user_document_tag'),
    )

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test database connection
def test_connection():
    """Test database connection"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1")).fetchone()
        db.close()
        logger.info("Database connection successful!")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
