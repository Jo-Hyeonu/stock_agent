import httpx
from typing import List, Dict, Optional
import asyncio
from datetime import datetime, timedelta
import logging
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.portfolio import Portfolio

logger = logging.getLogger(__name__)

class StockPriceService:
    def __init__(self, api_key: str = None):
        settings = get_settings()
        self.api_key = api_key or settings.STOCK_API_KEY
        if not self.api_key:
            logger.warning("공공데이터 포털 API 키가 설정되지 않았습니다.")
        
        self.base_url = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def get_stock_price(self, stock_code: str, stock_name: str) -> Optional[Dict]:
        """개별 종목의 현재 가격 조회"""
        if not self.api_key:
            logger.error("API 키가 설정되지 않았습니다.")
            return None
            
        try:
            # 최근 영업일 날짜 계산 (주말 제외)
            today = datetime.now()
            date = today
            
            # 주말인 경우 금요일로 설정
            while date.weekday() >= 5:  # 5=토요일, 6=일요일
                date = date - timedelta(days=1)
            
            date_str = date.strftime("%Y%m%d")
            
            # API 요청 URL 구성
            url = f"{self.base_url}/getStockPriceInfo"
            params = {
                "serviceKey": self.api_key,
                "numOfRows": 10,
                "pageNo": 1,
                "resultType": "json",
                "endbasDt": date_str,
                "likeItmsNm": stock_name
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"API 요청 실패 ({stock_name}): {response.status_code}")
                    return None
                
                data = response.json()
                
                # 응답 데이터 파싱
                if "response" in data and "body" in data["response"]:
                    items = data["response"]["body"].get("items", {})
                    
                    if isinstance(items, dict) and "item" in items:
                        items_list = items["item"]
                        if not isinstance(items_list, list):
                            items_list = [items_list]
                        
                        # 종목 코드가 일치하는 항목 찾기
                        for item in items_list:
                            if item.get("srtnCd") == stock_code:
                                return self._parse_stock_data(item)
                        
                        # 종목 코드가 정확히 일치하지 않으면 첫 번째 항목 반환
                        if items_list:
                            return self._parse_stock_data(items_list[0])
                
                logger.warning(f"종목 데이터를 찾을 수 없습니다: {stock_name} ({stock_code})")
                return None
                
        except Exception as e:
            logger.error(f"주식 가격 조회 오류 ({stock_name}): {e}")
            return None
    
    def _parse_stock_data(self, item: Dict) -> Dict:
        """API 응답 데이터를 파싱하여 표준 형식으로 변환"""
        try:
            current_price = float(item.get("clpr", 0))  # 종가
            prev_price = float(item.get("vs", 0))  # 전일 대비
            
            # 변동률 계산
            if current_price > 0 and prev_price != 0:
                change_rate = (prev_price / (current_price - prev_price)) * 100
            else:
                change_rate = 0.0
            
            # 변동 방향 결정
            if prev_price > 0:
                change_str = f"+{prev_price:,.0f} (+{change_rate:.2f}%)"
            elif prev_price < 0:
                change_str = f"{prev_price:,.0f} ({change_rate:.2f}%)"
            else:
                change_str = "0 (0.00%)"
            
            return {
                "stock_code": item.get("srtnCd", ""),
                "stock_name": item.get("itmsNm", ""),
                "current_price": current_price,
                "change_amount": prev_price,
                "change_rate": change_rate,
                "change_str": change_str,
                "volume": int(item.get("trqu", 0)),  # 거래량
                "market_cap": int(item.get("mrktTotAmt", 0)),  # 시가총액
                "high_price": float(item.get("hipr", 0)),  # 고가
                "low_price": float(item.get("lopr", 0)),  # 저가
                "open_price": float(item.get("mkp", 0)),  # 시가
                "updated_at": datetime.now().isoformat(),
                "base_date": item.get("basDt", "")
            }
            
        except (ValueError, KeyError) as e:
            logger.error(f"주식 데이터 파싱 오류: {e}")
            return {}
    
    async def get_multiple_stock_prices(self, stocks: List[Dict[str, str]]) -> List[Dict]:
        """여러 종목의 가격을 한 번에 조회"""
        tasks = []
        
        for stock in stocks:
            task = self.get_stock_price(stock["code"], stock["name"])
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, dict) and result:
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"주식 가격 조회 실패 ({stocks[i]['name']}): {result}")
        
        return valid_results
    
    async def update_portfolio_prices(self, db: Session, user_id: int) -> List[Dict]:
        """사용자 포트폴리오의 모든 종목 가격 업데이트"""
        
        # 사용자 포트폴리오 조회
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        
        if not portfolios:
            logger.info(f"사용자 {user_id}의 포트폴리오가 없습니다.")
            return []
        
        # 종목 정보 리스트 생성
        stocks = [
            {"code": p.stock_code, "name": p.stock_name}
            for p in portfolios
        ]
        
        # 가격 정보 조회
        price_data = await self.get_multiple_stock_prices(stocks)
        
        # 데이터베이스 업데이트
        updated_portfolios = []
        
        for portfolio in portfolios:
            # 해당 종목의 가격 데이터 찾기
            stock_price = next(
                (data for data in price_data 
                 if data.get("stock_code") == portfolio.stock_code),
                None
            )
            
            if stock_price and stock_price.get("current_price", 0) > 0:
                # 포트폴리오 현재가 업데이트
                old_price = portfolio.current_price
                portfolio.current_price = stock_price["current_price"]
                
                # 평가손익 계산
                total_value = portfolio.quantity * portfolio.current_price
                total_cost = portfolio.quantity * portfolio.avg_price
                profit_loss = total_value - total_cost
                profit_loss_rate = (profit_loss / total_cost * 100) if total_cost > 0 else 0
                
                updated_portfolio = {
                    "portfolio_id": portfolio.id,
                    "stock_code": portfolio.stock_code,
                    "stock_name": portfolio.stock_name,
                    "quantity": portfolio.quantity,
                    "avg_price": portfolio.avg_price,
                    "old_price": old_price,
                    "current_price": portfolio.current_price,
                    "total_value": total_value,
                    "profit_loss": profit_loss,
                    "profit_loss_rate": profit_loss_rate,
                    "price_change": stock_price.get("change_str", ""),
                    "volume": stock_price.get("volume", 0),
                    "updated_at": stock_price.get("updated_at", "")
                }
                
                updated_portfolios.append(updated_portfolio)
                
                logger.info(f"{portfolio.stock_name} 가격 업데이트: {old_price:,} → {portfolio.current_price:,}")
            else:
                logger.warning(f"{portfolio.stock_name} 가격 정보를 가져올 수 없습니다.")
        
        # 데이터베이스 커밋
        try:
            db.commit()
            logger.info(f"총 {len(updated_portfolios)}개 종목 가격이 업데이트되었습니다.")
        except Exception as e:
            logger.error(f"가격 업데이트 커밋 실패: {e}")
            db.rollback()
        
        return updated_portfolios
    
    async def get_market_summary(self) -> Dict:
        """시장 전체 요약 정보 조회"""
        try:
            # 주요 지수들 조회 (코스피, 코스닥)
            major_indices = [
                {"code": "001", "name": "코스피"},
                {"code": "002", "name": "코스닥"}
            ]
            
            market_data = await self.get_multiple_stock_prices(major_indices)
            
            summary = {
                "updated_at": datetime.now().isoformat(),
                "indices": market_data,
                "status": "정상" if market_data else "데이터 없음"
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"시장 요약 정보 조회 오류: {e}")
            return {
                "updated_at": datetime.now().isoformat(),
                "indices": [],
                "status": "오류"
            }
    
    def is_market_open(self) -> bool:
        """장 시간 여부 확인 (한국 시간 기준)"""
        now = datetime.now()
        
        # 주말 체크
        if now.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # 장 시간: 09:00 ~ 15:30
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
