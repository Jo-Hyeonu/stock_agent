import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 데이터베이스 설정
    DATABASE_URL: str = "sqlite:///./finance_ai.db"
    
    # Gemini API 설정
    GEMINI_API_KEY: str = ""
    
    # 공공데이터 포털 주식 API 설정
    STOCK_API_KEY: str = ""
    
    # 애플리케이션 설정
    APP_NAME: str = "Finance AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # CORS 설정
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # 뉴스 크롤링 설정
    NEWS_CRAWL_INTERVAL_MINUTES: int = 60  # 1시간마다
    MAX_NEWS_PER_KEYWORD: int = 10
    NEWS_RELEVANCE_THRESHOLD: float = 0.5
    
    # 전략 업데이트 설정
    STRATEGY_UPDATE_INTERVAL_MINUTES: int = 120  # 2시간마다
    STRATEGY_CONFIDENCE_THRESHOLD: float = 0.7
    
    # 주식 가격 업데이트 설정
    PRICE_UPDATE_INTERVAL_MINUTES: int = 5  # 5분마다
    MARKET_OPEN_HOUR: int = 9  # 장 시작 시간
    MARKET_CLOSE_HOUR: int = 15  # 장 마감 시간
    MARKET_CLOSE_MINUTE: int = 30  # 장 마감 분
    
    # 알림 설정
    NOTIFICATION_ENABLED: bool = True
    HIGH_IMPACT_NEWS_THRESHOLD: float = 0.8
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()