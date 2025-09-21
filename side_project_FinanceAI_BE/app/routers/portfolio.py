from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import logging

from ..db.database import get_db
from ..models.portfolio import Portfolio, Strategy, NewsSummary, NewsKeyword
from ..services.strategy_service import StrategyService
from ..services.notification_service import notification_service
from ..services.stock_price_service import StockPriceService
from ..core.config import get_settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Pydantic 모델들
class PortfolioCreate(BaseModel):
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float

class PortfolioUpdate(BaseModel):
    quantity: Optional[int] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None

class KeywordAdd(BaseModel):
    keyword: str
    priority: int = 1

class PortfolioResponse(BaseModel):
    id: int
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float
    current_price: float
    created_at: str
    
    class Config:
        from_attributes = True

class StrategyResponse(BaseModel):
    id: int
    strategy_type: str
    confidence: float
    reasoning: str
    target_price: Optional[float]
    is_changed: bool
    created_at: str
    
    class Config:
        from_attributes = True

# 의존성: StrategyService 인스턴스
def get_strategy_service():
    settings = get_settings()
    return StrategyService(settings.GEMINI_API_KEY)

# 의존성: StockPriceService 인스턴스
def get_stock_price_service():
    settings = get_settings()
    return StockPriceService(settings.STOCK_API_KEY)

@router.post("/", response_model=PortfolioResponse)
async def create_portfolio(
    portfolio: PortfolioCreate,
    user_id: int = 1,  # 임시로 고정값 사용 (실제로는 JWT 토큰에서 추출)
    db: Session = Depends(get_db)
):
    """포트폴리오 종목 추가"""
    try:
        # 중복 체크
        existing = db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.stock_code == portfolio.stock_code
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="이미 포트폴리오에 있는 종목입니다.")
        
        db_portfolio = Portfolio(
            user_id=user_id,
            stock_code=portfolio.stock_code,
            stock_name=portfolio.stock_name,
            quantity=portfolio.quantity,
            avg_price=portfolio.avg_price,
            current_price=portfolio.avg_price  # 초기값은 매입가로 설정
        )
        
        db.add(db_portfolio)
        db.commit()
        db.refresh(db_portfolio)
        
        logger.info(f"포트폴리오 추가: {portfolio.stock_name} ({portfolio.stock_code})")
        
        return PortfolioResponse(
            id=db_portfolio.id,
            stock_code=db_portfolio.stock_code,
            stock_name=db_portfolio.stock_name,
            quantity=db_portfolio.quantity,
            avg_price=db_portfolio.avg_price,
            current_price=db_portfolio.current_price,
            created_at=db_portfolio.created_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"포트폴리오 추가 오류: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="포트폴리오 추가 중 오류가 발생했습니다.")

@router.get("/", response_model=List[PortfolioResponse])
async def get_portfolios(
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """사용자 포트폴리오 목록 조회"""
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
    
    return [
        PortfolioResponse(
            id=p.id,
            stock_code=p.stock_code,
            stock_name=p.stock_name,
            quantity=p.quantity,
            avg_price=p.avg_price,
            current_price=p.current_price,
            created_at=p.created_at.isoformat()
        )
        for p in portfolios
    ]

@router.put("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    portfolio_update: PortfolioUpdate,
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """포트폴리오 종목 수정"""
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오 종목을 찾을 수 없습니다.")
    
    if portfolio_update.quantity is not None:
        portfolio.quantity = portfolio_update.quantity
    if portfolio_update.avg_price is not None:
        portfolio.avg_price = portfolio_update.avg_price
    if portfolio_update.current_price is not None:
        portfolio.current_price = portfolio_update.current_price
    
    db.commit()
    db.refresh(portfolio)
    
    return PortfolioResponse(
        id=portfolio.id,
        stock_code=portfolio.stock_code,
        stock_name=portfolio.stock_name,
        quantity=portfolio.quantity,
        avg_price=portfolio.avg_price,
        current_price=portfolio.current_price,
        created_at=portfolio.created_at.isoformat()
    )

@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: int,
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """포트폴리오 종목 삭제"""
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오 종목을 찾을 수 없습니다.")
    
    db.delete(portfolio)
    db.commit()
    
    return {"message": "포트폴리오 종목이 삭제되었습니다."}

@router.post("/update-strategies")
async def update_all_strategies(
    background_tasks: BackgroundTasks,
    user_id: int = 1,
    db: Session = Depends(get_db),
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """모든 포트폴리오 전략 업데이트"""
    
    async def update_strategies_task():
        try:
            strategy_updates = await strategy_service.update_portfolio_strategies(db, user_id)
            
            # 전략 변경이 있는 경우 알림 전송
            changed_strategies = [update for update in strategy_updates if update['changed']]
            if changed_strategies:
                await notification_service.process_strategy_changes(user_id, changed_strategies)
                
            logger.info(f"전략 업데이트 완료: 총 {len(strategy_updates)}건, 변경 {len(changed_strategies)}건")
            
        except Exception as e:
            logger.error(f"전략 업데이트 오류: {e}")
    
    background_tasks.add_task(update_strategies_task)
    
    return {"message": "전략 업데이트가 백그라운드에서 시작되었습니다."}

@router.get("/{portfolio_id}/strategies", response_model=List[StrategyResponse])
async def get_portfolio_strategies(
    portfolio_id: int,
    limit: int = 10,
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """포트폴리오 전략 히스토리 조회"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    strategies = db.query(Strategy).filter(
        Strategy.portfolio_id == portfolio_id
    ).order_by(Strategy.created_at.desc()).limit(limit).all()
    
    return [
        StrategyResponse(
            id=s.id,
            strategy_type=s.strategy_type,
            confidence=s.confidence,
            reasoning=s.reasoning,
            target_price=s.target_price,
            is_changed=s.is_changed,
            created_at=s.created_at.isoformat()
        )
        for s in strategies
    ]

@router.get("/{portfolio_id}/news-summary")
async def get_portfolio_news_summary(
    portfolio_id: int,
    days: int = 7,
    user_id: int = 1,
    db: Session = Depends(get_db),
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """포트폴리오 뉴스 요약 조회"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    news_summary = await strategy_service.get_portfolio_news_summary(db, portfolio_id, days)
    
    return {
        "portfolio_id": portfolio_id,
        "stock_name": portfolio.stock_name,
        "period_days": days,
        **news_summary
    }

@router.post("/{portfolio_id}/keywords")
async def add_custom_keyword(
    portfolio_id: int,
    keyword_data: KeywordAdd,
    user_id: int = 1,
    db: Session = Depends(get_db),
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """커스텀 키워드 추가"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    success = await strategy_service.add_custom_keyword(
        db, portfolio_id, keyword_data.keyword, keyword_data.priority
    )
    
    if success:
        return {"message": f"키워드 '{keyword_data.keyword}'가 추가되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="키워드 추가 중 오류가 발생했습니다.")

@router.delete("/{portfolio_id}/keywords/{keyword}")
async def remove_custom_keyword(
    portfolio_id: int,
    keyword: str,
    user_id: int = 1,
    db: Session = Depends(get_db),
    strategy_service: StrategyService = Depends(get_strategy_service)
):
    """커스텀 키워드 제거"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    success = await strategy_service.remove_custom_keyword(db, portfolio_id, keyword)
    
    if success:
        return {"message": f"키워드 '{keyword}'가 제거되었습니다."}
    else:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다.")

@router.get("/{portfolio_id}/keywords")
async def get_custom_keywords(
    portfolio_id: int,
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """포트폴리오 커스텀 키워드 목록 조회"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    keywords = db.query(NewsKeyword).filter(
        NewsKeyword.portfolio_id == portfolio_id,
        NewsKeyword.is_active == True
    ).all()
    
    return [
        {
            "id": k.id,
            "keyword": k.keyword,
            "priority": k.priority,
            "created_at": k.created_at.isoformat()
        }
        for k in keywords
    ]

@router.post("/update-prices")
async def update_portfolio_prices(
    background_tasks: BackgroundTasks,
    user_id: int = 1,
    db: Session = Depends(get_db),
    stock_price_service: StockPriceService = Depends(get_stock_price_service)
):
    """포트폴리오 모든 종목의 현재 가격 업데이트"""
    
    async def update_prices_task():
        try:
            updated_portfolios = await stock_price_service.update_portfolio_prices(db, user_id)
            
            if updated_portfolios:
                # WebSocket으로 가격 업데이트 알림 전송
                await notification_service.manager.send_price_update_notification(user_id, updated_portfolios)
                logger.info(f"가격 업데이트 완료: {len(updated_portfolios)}개 종목")
            else:
                logger.warning("업데이트된 가격 정보가 없습니다.")
                
        except Exception as e:
            logger.error(f"가격 업데이트 오류: {e}")
    
    background_tasks.add_task(update_prices_task)
    
    return {"message": "가격 업데이트가 백그라운드에서 시작되었습니다."}

@router.get("/{portfolio_id}/price-info")
async def get_portfolio_price_info(
    portfolio_id: int,
    user_id: int = 1,
    db: Session = Depends(get_db),
    stock_price_service: StockPriceService = Depends(get_stock_price_service)
):
    """개별 포트폴리오 종목의 상세 가격 정보 조회"""
    
    # 포트폴리오 소유권 확인
    portfolio = db.query(Portfolio).filter(
        Portfolio.id == portfolio_id,
        Portfolio.user_id == user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
    
    # 실시간 가격 정보 조회
    price_info = await stock_price_service.get_stock_price(portfolio.stock_code, portfolio.stock_name)
    
    if not price_info:
        raise HTTPException(status_code=503, detail="가격 정보를 가져올 수 없습니다.")
    
    # 포트폴리오 정보와 결합
    total_value = portfolio.quantity * price_info.get("current_price", 0)
    total_cost = portfolio.quantity * portfolio.avg_price
    profit_loss = total_value - total_cost
    profit_loss_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0
    
    return {
        "portfolio_id": portfolio.id,
        "stock_code": portfolio.stock_code,
        "stock_name": portfolio.stock_name,
        "quantity": portfolio.quantity,
        "avg_price": portfolio.avg_price,
        "current_price": price_info.get("current_price", 0),
        "total_value": total_value,
        "total_cost": total_cost,
        "profit_loss": profit_loss,
        "profit_loss_rate": profit_loss_rate,
        "price_info": price_info
    }

@router.get("/market-summary")
async def get_market_summary(
    stock_price_service: StockPriceService = Depends(get_stock_price_service)
):
    """시장 전체 요약 정보 조회"""
    
    market_summary = await stock_price_service.get_market_summary()
    market_status = "장중" if stock_price_service.is_market_open() else "장마감"
    
    return {
        "market_status": market_status,
        "is_market_open": stock_price_service.is_market_open(),
        **market_summary
    }

@router.get("/price-status")
async def get_price_update_status(
    user_id: int = 1,
    db: Session = Depends(get_db)
):
    """가격 업데이트 상태 확인"""
    
    portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
    
    if not portfolios:
        return {"message": "포트폴리오가 없습니다.", "portfolios": []}
    
    portfolio_status = []
    for portfolio in portfolios:
        portfolio_status.append({
            "id": portfolio.id,
            "stock_name": portfolio.stock_name,
            "stock_code": portfolio.stock_code,
            "current_price": portfolio.current_price,
            "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None
        })
    
    return {
        "total_portfolios": len(portfolios),
        "portfolios": portfolio_status,
        "last_check": datetime.now().isoformat()
    }
