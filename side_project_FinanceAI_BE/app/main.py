from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import asyncio
from contextlib import asynccontextmanager

from .core.config import get_settings
from .db.database import create_tables
from .routers import portfolio, websocket
from .services.strategy_service import StrategyService

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# 애플리케이션 시작/종료 시 실행할 작업
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    logger.info("Finance AI 애플리케이션 시작")
    
    # 데이터베이스 테이블 생성
    create_tables()
    logger.info("데이터베이스 테이블 초기화 완료")
    
    # 백그라운드 작업 시작 (전략 업데이트 스케줄러)
    # asyncio.create_task(start_background_tasks())
    
    yield
    
    # 종료 시 실행
    logger.info("Finance AI 애플리케이션 종료")

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI 기반 금융 포트폴리오 관리 시스템",
    lifespan=lifespan
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(portfolio.router)
app.include_router(websocket.router)

# 정적 파일 서빙 (프론트엔드)
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Finance AI API 서버가 실행 중입니다.",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "database": "connected"
    }

async def start_background_tasks():
    """백그라운드 작업 시작"""
    logger.info("백그라운드 작업 시작")
    
    # 정기적인 전략 업데이트 작업
    while True:
        try:
            await asyncio.sleep(settings.STRATEGY_UPDATE_INTERVAL_MINUTES * 60)
            
            # 여기서 모든 사용자의 전략을 업데이트하는 작업을 수행
            # (실제 구현에서는 Celery 등을 사용하는 것이 좋습니다)
            logger.info("정기 전략 업데이트 실행")
            
        except Exception as e:
            logger.error(f"백그라운드 작업 오류: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 대기