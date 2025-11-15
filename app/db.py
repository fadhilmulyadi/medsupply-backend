
import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL tidak diset. "
        "Pastikan file .env berisi baris:\n"
        "DATABASE_URL=postgresql://postgres:password@host:5432/dbname?sslmode=require"
    )

# DEBUG ringan: tampilkan host (tanpa password)
try:
    # jangan sampai error kalau format aneh
    after_at = DATABASE_URL.split("@", 1)[1] if "@" in DATABASE_URL else DATABASE_URL
    print(">>> DATABASE_URL (setelah @):", after_at.split("?")[0])
except Exception:
    print(">>> DATABASE_URL terbaca, tapi tidak bisa di-parse untuk debug")

# Engine utama
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency untuk FastAPI kalau nanti butuh Session ORM.
    Sekarang fokus kita ke pandas, tapi ini disiapkan saja.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        raise e
    finally:
        db.close()
