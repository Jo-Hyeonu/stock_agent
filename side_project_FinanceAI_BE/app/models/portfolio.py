from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..db.database import Base

class Portfolio(Base):
    __tablename__ = "portfolios"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_code = Column(String(20), nullable=False)  # 종목 코드 (예: 005930)
    stock_name = Column(String(100), nullable=False)  # 종목명 (예: 삼성전자)
    quantity = Column(Integer, nullable=False)  # 보유 수량
    avg_price = Column(Float, nullable=False)  # 평균 매입가
    current_price = Column(Float, default=0)  # 현재가
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    user = relationship("User", back_populates="portfolios")
    news_summaries = relationship("NewsSummary", back_populates="portfolio")
    strategies = relationship("Strategy", back_populates="portfolio")

class NewsSummary(Base):
    __tablename__ = "news_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    news_title = Column(String(500), nullable=False)
    news_url = Column(Text, nullable=False)
    news_content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)  # AI가 요약한 내용
    sentiment = Column(String(20))  # 긍정적/부정적/중립적
    relevance_score = Column(Float, default=0)  # 관련도 점수 (0-1)
    published_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계 설정
    portfolio = relationship("Portfolio", back_populates="news_summaries")

class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    strategy_type = Column(String(20), nullable=False)  # BUY, SELL, HOLD
    confidence = Column(Float, default=0)  # 신뢰도 (0-1)
    reasoning = Column(Text, nullable=False)  # AI가 생성한 전략 근거
    target_price = Column(Float)  # 목표가 (선택사항)
    previous_strategy = Column(String(20))  # 이전 전략
    is_changed = Column(Boolean, default=False)  # 전략 변경 여부
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계 설정
    portfolio = relationship("Portfolio", back_populates="strategies")

class NewsKeyword(Base):
    __tablename__ = "news_keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    keyword = Column(String(100), nullable=False)  # 검색 키워드
    priority = Column(Integer, default=1)  # 우선순위 (1-5)
    is_active = Column(Boolean, default=True)  # 활성화 여부
    created_at = Column(DateTime, default=datetime.utcnow)
