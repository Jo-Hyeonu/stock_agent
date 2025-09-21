from typing import List, Dict, Optional
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .news_crawler import NewsCrawler
from .gemini_service import GeminiService, StrategyResult
from ..models.portfolio import Portfolio, NewsSummary, Strategy, NewsKeyword
from ..db.database import get_db

logger = logging.getLogger(__name__)

class StrategyService:
    def __init__(self, gemini_api_key: str):
        self.news_crawler = NewsCrawler()
        self.gemini_service = GeminiService(gemini_api_key)
        
    async def update_portfolio_strategies(self, db: Session, user_id: int) -> List[Dict]:
        """사용자의 모든 포트폴리오에 대해 전략 업데이트"""
        
        # 사용자의 포트폴리오 조회
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        
        if not portfolios:
            logger.info(f"사용자 {user_id}의 포트폴리오가 없습니다.")
            return []
        
        strategy_updates = []
        
        for portfolio in portfolios:
            try:
                logger.info(f"포트폴리오 {portfolio.stock_name} 전략 업데이트 시작")
                
                # 1. 뉴스 크롤링
                keywords = await self._get_portfolio_keywords(db, portfolio)
                news_articles = await self.news_crawler.crawl_news_for_keywords(keywords, max_articles_per_keyword=5)
                
                # 2. 뉴스 요약
                summarized_news = await self.gemini_service.summarize_news_articles(news_articles, portfolio.stock_name)
                
                # 3. 뉴스 저장
                await self._save_news_summaries(db, portfolio.id, summarized_news)
                
                # 4. 전략 생성
                previous_strategy = await self._get_latest_strategy(db, portfolio.id)
                portfolio_info = {
                    'quantity': portfolio.quantity,
                    'avg_price': portfolio.avg_price
                }
                
                new_strategy = await self.gemini_service.generate_investment_strategy(
                    stock_name=portfolio.stock_name,
                    stock_code=portfolio.stock_code,
                    current_price=portfolio.current_price,
                    portfolio_info=portfolio_info,
                    news_summaries=summarized_news,
                    previous_strategy=previous_strategy.strategy_type if previous_strategy else None
                )
                
                # 5. 전략 저장 및 변경 감지
                strategy_changed = await self._save_strategy(db, portfolio.id, new_strategy, previous_strategy)
                
                strategy_update = {
                    'portfolio_id': portfolio.id,
                    'stock_name': portfolio.stock_name,
                    'stock_code': portfolio.stock_code,
                    'previous_strategy': previous_strategy.strategy_type if previous_strategy else None,
                    'new_strategy': new_strategy.strategy_type,
                    'changed': strategy_changed,
                    'confidence': new_strategy.confidence,
                    'reasoning': new_strategy.reasoning,
                    'news_count': len(summarized_news)
                }
                
                strategy_updates.append(strategy_update)
                
                logger.info(f"포트폴리오 {portfolio.stock_name} 전략 업데이트 완료: {new_strategy.strategy_type}")
                
            except Exception as e:
                logger.error(f"포트폴리오 {portfolio.stock_name} 전략 업데이트 오류: {e}")
                continue
        
        db.commit()
        return strategy_updates
    
    async def _get_portfolio_keywords(self, db: Session, portfolio: Portfolio) -> List[str]:
        """포트폴리오별 검색 키워드 생성"""
        
        # 기본 키워드: 종목명, 종목코드
        keywords = [portfolio.stock_name, portfolio.stock_code]
        
        # 저장된 커스텀 키워드 조회
        custom_keywords = db.query(NewsKeyword).filter(
            NewsKeyword.portfolio_id == portfolio.id,
            NewsKeyword.is_active == True
        ).all()
        
        for keyword in custom_keywords:
            keywords.append(keyword.keyword)
        
        # 기업명에서 파생된 키워드 생성
        if '전자' in portfolio.stock_name:
            keywords.extend([f"{portfolio.stock_name} 실적", f"{portfolio.stock_name} 매출"])
        elif '바이오' in portfolio.stock_name or '제약' in portfolio.stock_name:
            keywords.extend([f"{portfolio.stock_name} 신약", f"{portfolio.stock_name} 임상"])
        elif '자동차' in portfolio.stock_name or '차' in portfolio.stock_name:
            keywords.extend([f"{portfolio.stock_name} 판매", f"{portfolio.stock_name} 전기차"])
        
        return list(set(keywords))  # 중복 제거
    
    async def _save_news_summaries(self, db: Session, portfolio_id: int, news_summaries: List[Dict]):
        """뉴스 요약 저장"""
        
        for news in news_summaries:
            try:
                # 중복 체크 (URL 기준)
                existing = db.query(NewsSummary).filter(
                    NewsSummary.portfolio_id == portfolio_id,
                    NewsSummary.news_url == news['url']
                ).first()
                
                if existing:
                    continue  # 이미 존재하는 뉴스는 스킵
                
                news_summary = NewsSummary(
                    portfolio_id=portfolio_id,
                    news_title=news['title'],
                    news_url=news['url'],
                    news_content=news['content'],
                    summary=news.get('summary', ''),
                    sentiment=news.get('sentiment', 'NEUTRAL'),
                    relevance_score=news.get('relevance_score', 0.0),
                    published_at=news['published_at']
                )
                
                db.add(news_summary)
                
            except Exception as e:
                logger.error(f"뉴스 요약 저장 오류: {e}")
                continue
    
    async def _get_latest_strategy(self, db: Session, portfolio_id: int) -> Optional[Strategy]:
        """최신 전략 조회"""
        return db.query(Strategy).filter(
            Strategy.portfolio_id == portfolio_id
        ).order_by(Strategy.created_at.desc()).first()
    
    async def _save_strategy(self, db: Session, portfolio_id: int, new_strategy: StrategyResult, previous_strategy: Optional[Strategy]) -> bool:
        """새 전략 저장 및 변경 여부 반환"""
        
        # 전략 변경 여부 확인
        strategy_changed = (
            previous_strategy is None or 
            previous_strategy.strategy_type != new_strategy.strategy_type
        )
        
        # 새 전략 저장
        strategy = Strategy(
            portfolio_id=portfolio_id,
            strategy_type=new_strategy.strategy_type,
            confidence=new_strategy.confidence,
            reasoning=new_strategy.reasoning,
            target_price=new_strategy.target_price,
            previous_strategy=previous_strategy.strategy_type if previous_strategy else None,
            is_changed=strategy_changed
        )
        
        db.add(strategy)
        
        return strategy_changed
    
    async def get_strategy_changes(self, db: Session, user_id: int, hours: int = 24) -> List[Dict]:
        """최근 전략 변경 내역 조회"""
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # 사용자의 포트폴리오 ID 목록
        portfolio_ids = db.query(Portfolio.id).filter(Portfolio.user_id == user_id).subquery()
        
        # 전략 변경 내역 조회
        strategy_changes = db.query(Strategy).filter(
            Strategy.portfolio_id.in_(portfolio_ids),
            Strategy.is_changed == True,
            Strategy.created_at >= since
        ).join(Portfolio).all()
        
        changes = []
        for strategy in strategy_changes:
            changes.append({
                'portfolio_id': strategy.portfolio_id,
                'stock_name': strategy.portfolio.stock_name,
                'stock_code': strategy.portfolio.stock_code,
                'previous_strategy': strategy.previous_strategy,
                'new_strategy': strategy.strategy_type,
                'confidence': strategy.confidence,
                'reasoning': strategy.reasoning,
                'changed_at': strategy.created_at.isoformat()
            })
        
        return changes
    
    async def add_custom_keyword(self, db: Session, portfolio_id: int, keyword: str, priority: int = 1) -> bool:
        """포트폴리오에 커스텀 키워드 추가"""
        
        try:
            # 중복 체크
            existing = db.query(NewsKeyword).filter(
                NewsKeyword.portfolio_id == portfolio_id,
                NewsKeyword.keyword == keyword
            ).first()
            
            if existing:
                existing.is_active = True
                existing.priority = priority
            else:
                news_keyword = NewsKeyword(
                    portfolio_id=portfolio_id,
                    keyword=keyword,
                    priority=priority
                )
                db.add(news_keyword)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"커스텀 키워드 추가 오류: {e}")
            db.rollback()
            return False
    
    async def remove_custom_keyword(self, db: Session, portfolio_id: int, keyword: str) -> bool:
        """포트폴리오에서 커스텀 키워드 제거"""
        
        try:
            news_keyword = db.query(NewsKeyword).filter(
                NewsKeyword.portfolio_id == portfolio_id,
                NewsKeyword.keyword == keyword
            ).first()
            
            if news_keyword:
                news_keyword.is_active = False
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"커스텀 키워드 제거 오류: {e}")
            db.rollback()
            return False
    
    async def get_portfolio_news_summary(self, db: Session, portfolio_id: int, days: int = 7) -> Dict:
        """포트폴리오별 뉴스 요약 통계"""
        
        since = datetime.utcnow() - timedelta(days=days)
        
        news_summaries = db.query(NewsSummary).filter(
            NewsSummary.portfolio_id == portfolio_id,
            NewsSummary.created_at >= since
        ).all()
        
        if not news_summaries:
            return {
                'total_count': 0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'avg_relevance': 0.0,
                'latest_news': []
            }
        
        positive_count = sum(1 for news in news_summaries if news.sentiment == 'POSITIVE')
        negative_count = sum(1 for news in news_summaries if news.sentiment == 'NEGATIVE')
        neutral_count = len(news_summaries) - positive_count - negative_count
        
        avg_relevance = sum(news.relevance_score for news in news_summaries) / len(news_summaries)
        
        # 최신 뉴스 5개
        latest_news = sorted(news_summaries, key=lambda x: x.published_at, reverse=True)[:5]
        latest_news_data = [
            {
                'title': news.news_title,
                'summary': news.summary,
                'sentiment': news.sentiment,
                'relevance_score': news.relevance_score,
                'published_at': news.published_at.isoformat()
            }
            for news in latest_news
        ]
        
        return {
            'total_count': len(news_summaries),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'avg_relevance': round(avg_relevance, 2),
            'latest_news': latest_news_data
        }
