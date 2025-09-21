from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..core.config import get_settings

settings = get_settings()

# SQLite 데이터베이스 엔진 생성
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite용 설정
)

# 세션 로컬 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()

# 데이터베이스 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 데이터베이스 테이블 생성
def create_tables():
    from ..models.portfolio import Base as PortfolioBase
    from ..models.user import Base as UserBase
    
    # 모든 테이블 생성
    Base.metadata.create_all(bind=engine)
    PortfolioBase.metadata.create_all(bind=engine)
    if hasattr(UserBase, 'metadata'):
        UserBase.metadata.create_all(bind=engine)
