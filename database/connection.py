"""
Database Connection Manager
Handles SQLite connection, session management, and initialization
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "assistant.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = None
SessionLocal = None


def get_engine():
    """Get or create database engine"""
    global engine
    if engine is None:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


def get_session_factory():
    """Get or create session factory"""
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return SessionLocal


def init_database():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def drop_database():
    """Drop all tables (for testing)"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_db():
    """FastAPI dependency for database sessions"""
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


class DatabaseManager:
    """High-level database operations manager"""
    
    def __init__(self):
        self.engine = get_engine()
        self.SessionLocal = get_session_factory()
        init_database()
    
    def create_session(self) -> Session:
        return self.SessionLocal()
    
    @contextmanager
    def session_scope(self):
        session = self.create_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


db_manager = DatabaseManager()
