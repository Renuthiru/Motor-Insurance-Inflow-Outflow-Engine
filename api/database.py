# ============================================================
# database.py
# ============================================================
# Purpose : Manages the MySQL database connection for the API.
#           This file does ONLY connection setup — no business logic,
#           no queries, no routes. Just the "phone line" to MySQL.
#
# Concepts:
#   engine  → SQLAlchemy's connection pool manager.
#             It reads the DB_URL and maintains reusable connections.
#   Session → A single conversation with the database.
#             Each API request gets its own session.
#   get_db  → A FastAPI dependency. FastAPI calls this automatically
#             for any route that needs database access.
# ============================================================

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# -----------------------------------------------------------
# Load environment variables from the .env file.
# This makes DB_HOST, DB_USER, DB_PASSWORD, etc. available
# as os.environ values — without hard-coding them here.
# -----------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------
# Read each credential from environment variables.
# If a variable is missing, use a safe default or raise an error.
# -----------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "inflow_db")

# -----------------------------------------------------------
# Build the database URL using SQLAlchemy's URL.create().
#
# WHY NOT a plain f-string URL?
# If your password contains special characters like @ or # or /,
# a plain string URL breaks because those characters have special
# meaning in URLs (e.g. @ separates credentials from host).
#
# URL.create() handles this safely — it encodes special characters
# automatically, so your password is used exactly as written in .env.
#
# This is the recommended production approach.
# -----------------------------------------------------------
from sqlalchemy.engine import URL

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,      # Special chars (@, #, /, etc.) handled safely
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

# -----------------------------------------------------------
# Create the Engine.
# The engine is SQLAlchemy's core connection manager.
# pool_pre_ping=True means: before using any connection from the pool,
# test if it's still alive. This prevents "stale connection" errors
# when MySQL drops idle connections.
# -----------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# -----------------------------------------------------------
# Create the SessionLocal class.
# This is a factory — calling SessionLocal() creates a new session.
# autocommit=False → We control when to commit (safe default).
# autoflush=False  → We control when to flush changes (safe default).
# bind=engine      → Each session uses our engine's connection pool.
# -----------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# -----------------------------------------------------------
# Base class for ORM models (used later when we define table models).
# We define it here so all models can import from one place.
# -----------------------------------------------------------
class Base(DeclarativeBase):
    pass


# -----------------------------------------------------------
# get_db — FastAPI Dependency.
# 
# A "dependency" in FastAPI is a function that FastAPI calls
# automatically before running your route handler.
# 
# How it works:
#   1. FastAPI sees that a route needs "db: Session"
#   2. FastAPI calls get_db()
#   3. get_db() opens a session (db = SessionLocal())
#   4. FastAPI passes that session into the route
#   5. After the route finishes, get_db() closes the session
#      (the "finally" block always runs — even if an error occurs)
# 
# This ensures every request gets a fresh session and it is
# always cleaned up, preventing connection leaks.
# -----------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------
# test_connection — Simple connection test (used during startup).
# Runs SELECT 1 which is the most harmless possible query.
# If this succeeds, the database is reachable and credentials work.
# -----------------------------------------------------------
def test_connection() -> dict:
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        return {"database": "connected", "db_name": DB_NAME, "host": DB_HOST}
    except Exception as e:
        return {"database": "error", "detail": str(e)}
