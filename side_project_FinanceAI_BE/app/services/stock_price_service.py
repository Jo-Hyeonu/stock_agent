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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        }
    
    async def get_stock_price(self, stock_code: str, stock_name: str) -> Optional[Dict]:
        """개별 종목의 현재 가격 조회"""
        if not self.api_key:
            logger.warning("API 키가 설정되지 않았습니다. 더미 데이터를 사용합니다.")
            return self._get_dummy_stock_data(stock_code, stock_name)
            
        try:
            # 최근 영업일 날짜 계산 (주말 제외)
            today = datetime.now()
            date = today
            
            # 주말인 경우 금요일로 설정
            while date.weekday() >= 5:  # 5=토요일, 6=일요일
                date = date - timedelta(days=1)
            
            date_str = date.strftime("%Y%m%d")
            
            # API 요청 URL 구성 (Kotlin 코드 참고)
            url = f"{self.base_url}/getStockPriceInfo"
            params = {
                "serviceKey": self.api_key,
                "numOfRows": 10,
                "pageNo": 1,
                "resultType": "json",
                "endbasDt": date_str,
                "likeItmsNm": stock_name
            }
            
            async with httpx.AsyncClient(timeout=30.0, verify=False, headers=self.headers) as client:
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
            logger.warning(f"주식 가격 조회 실패 ({stock_name}), 더미 데이터 사용: {e}")
            return self._get_dummy_stock_data(stock_code, stock_name)
    
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
                logger.warning(f"주식 가격 조회 실패 ({stocks[i]['name']}), 더미 데이터 사용: {result}")
        
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
            logger.warning(f"시장 요약 정보 조회 실패, 더미 데이터 사용: {e}")
            return {
                "updated_at": datetime.now().isoformat(),
                "indices": [],
                "status": "더미 데이터"
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
    
    async def search_stocks(self, query: str, limit: int = 20) -> List[Dict]:
        """종목 검색 API"""
        if not self.api_key:
            logger.warning("API 키가 설정되지 않았습니다. 더미 데이터를 사용합니다.")
            return self._get_dummy_search_results(query, limit)
            
        try:
            # 최근 영업일 날짜 계산
            today = datetime.now()
            date = today
            
            # 주말인 경우 금요일로 설정
            while date.weekday() >= 5:
                date = date - timedelta(days=1)
            
            date_str = date.strftime("%Y%m%d")
            
            # API 요청 URL 구성 (Kotlin 코드 참고)
            url = f"{self.base_url}/getStockPriceInfo"
            params = {
                "serviceKey": self.api_key,
                "numOfRows": limit,
                "pageNo": 1,
                "resultType": "json",
                "endbasDt": date_str,
                "likeItmsNm": query  # 종목명으로 검색
            }
            
            async with httpx.AsyncClient(timeout=30.0, verify=False, headers=self.headers) as client:
                response = await client.get(url, params=params, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"종목 검색 API 요청 실패: {response.status_code}")
                    return []
                
                data = response.json()
                stocks = []
                
                # 응답 데이터 파싱
                if "response" in data and "body" in data["response"]:
                    items = data["response"]["body"].get("items", {})
                    
                    if isinstance(items, dict) and "item" in items:
                        items_list = items["item"]
                        if not isinstance(items_list, list):
                            items_list = [items_list]
                        
                        for item in items_list:
                            stock_info = {
                                "stock_code": item.get("srtnCd", ""),
                                "stock_name": item.get("itmsNm", ""),
                                "market": self._get_market_type(item.get("mrktCtg", "")),
                                "current_price": float(item.get("clpr", 0)),
                                "change_rate": self._calculate_change_rate(item)
                            }
                            stocks.append(stock_info)
                
                return stocks
                
        except Exception as e:
            logger.warning(f"종목 검색 실패, 더미 데이터 사용: {e}")
            return self._get_dummy_search_results(query, limit)
    
    def _get_market_type(self, market_code: str) -> str:
        """시장 구분 코드를 시장명으로 변환"""
        market_map = {
            "KOSPI": "코스피",
            "KOSDAQ": "코스닥",
            "KONEX": "코넥스"
        }
        return market_map.get(market_code, "코스피")
    
    def _calculate_change_rate(self, item: Dict) -> float:
        """변동률 계산"""
        try:
            current_price = float(item.get("clpr", 0))
            prev_price = float(item.get("vs", 0))
            
            if current_price > 0 and prev_price != 0:
                return (prev_price / (current_price - prev_price)) * 100
            return 0.0
        except:
            return 0.0
    
    def _get_dummy_stock_data(self, stock_code: str, stock_name: str) -> Dict:
        """더미 주식 데이터 반환 (API 실패 시 사용)"""
        import random
        
        # 더미 가격 데이터 생성
        base_prices = {
            "005930": 75000,  # 삼성전자
            "000660": 120000, # SK하이닉스
            "035420": 450000, # NAVER
            "207940": 500000, # 삼성바이오로직스
            "006400": 80000,  # 삼성SDI
        }
        
        base_price = base_prices.get(stock_code, 50000)
        current_price = base_price + random.randint(-5000, 5000)
        change_amount = random.randint(-2000, 2000)
        change_rate = (change_amount / current_price) * 100
        
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": current_price,
            "change_amount": change_amount,
            "change_rate": change_rate,
            "change_str": f"{change_amount:+,.0f} ({change_rate:+.2f}%)",
            "volume": random.randint(100000, 1000000),
            "market_cap": current_price * random.randint(1000000, 10000000),
            "high_price": current_price + random.randint(0, 2000),
            "low_price": current_price - random.randint(0, 2000),
            "open_price": current_price + random.randint(-1000, 1000),
            "updated_at": datetime.now().isoformat(),
            "base_date": datetime.now().strftime("%Y%m%d")
        }
    
    def _get_dummy_search_results(self, query: str, limit: int) -> List[Dict]:
        """더미 검색 결과 반환 (API 실패 시 사용)"""
        import random
        
        # 주요 종목 데이터
        major_stocks = [
            {"code": "005930", "name": "삼성전자", "market": "코스피"},
            {"code": "000660", "name": "SK하이닉스", "market": "코스피"},
            {"code": "035420", "name": "NAVER", "market": "코스피"},
            {"code": "207940", "name": "삼성바이오로직스", "market": "코스피"},
            {"code": "006400", "name": "삼성SDI", "market": "코스피"},
            {"code": "035720", "name": "카카오", "market": "코스피"},
            {"code": "051910", "name": "LG화학", "market": "코스피"},
            {"code": "068270", "name": "셀트리온", "market": "코스피"},
            {"code": "000270", "name": "기아", "market": "코스피"},
            {"code": "323410", "name": "카카오뱅크", "market": "코스피"},
        ]
        
        # 검색어에 맞는 종목 필터링
        filtered_stocks = []
        for stock in major_stocks:
            if query.lower() in stock["name"].lower() or query in stock["code"]:
                filtered_stocks.append(stock)
        
        # 검색어가 없으면 모든 종목 반환
        if not filtered_stocks:
            filtered_stocks = major_stocks
        
        # 제한된 수만큼 반환
        results = []
        for stock in filtered_stocks[:limit]:
            base_price = random.randint(10000, 500000)
            current_price = base_price + random.randint(-5000, 5000)
            change_rate = random.uniform(-5.0, 5.0)
            
            results.append({
                "stock_code": stock["code"],
                "stock_name": stock["name"],
                "market": stock["market"],
                "current_price": current_price,
                "change_rate": change_rate
            })
        
        return results