import google.generativeai as genai
from typing import List, Dict, Optional
import json
import logging
from datetime import datetime
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StrategyResult:
    strategy_type: str  # BUY, SELL, HOLD
    confidence: float  # 0-1
    reasoning: str
    target_price: Optional[float] = None
    sentiment: str = "NEUTRAL"  # POSITIVE, NEGATIVE, NEUTRAL

class GeminiService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API 키가 설정되지 않았습니다. GEMINI_API_KEY 환경변수를 설정해주세요.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
    async def summarize_news_articles(self, articles: List[Dict], stock_name: str) -> List[Dict]:
        """뉴스 기사들을 요약"""
        summarized_articles = []
        
        for article in articles:
            try:
                summary = await self._summarize_single_article(article, stock_name)
                if summary:
                    article_with_summary = article.copy()
                    article_with_summary.update(summary)
                    summarized_articles.append(article_with_summary)
            except Exception as e:
                logger.error(f"뉴스 요약 오류 ({article.get('title', 'Unknown')}): {e}")
                continue
        
        return summarized_articles
    
    async def _summarize_single_article(self, article: Dict, stock_name: str) -> Optional[Dict]:
        """단일 뉴스 기사 요약"""
        prompt = f"""
다음은 '{stock_name}' 종목과 관련된 뉴스 기사입니다. 이 기사를 분석하여 다음 정보를 JSON 형태로 제공해주세요:

제목: {article.get('title', '')}
내용: {article.get('content', '')}

분석 결과를 다음 JSON 형식으로 작성해주세요:
{{
    "summary": "기사의 핵심 내용을 2-3문장으로 요약",
    "sentiment": "POSITIVE/NEGATIVE/NEUTRAL 중 하나",
    "relevance_score": 0.0-1.0 사이의 점수 (해당 종목과의 관련도),
    "key_points": ["주요 포인트1", "주요 포인트2", "주요 포인트3"]
}}

주의사항:
- sentiment는 해당 종목에 미치는 영향을 기준으로 판단
- relevance_score는 종목과의 직접적인 관련성을 0-1 점수로 평가
- key_points는 투자자가 알아야 할 핵심 사항들
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON 파싱
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()
            
            result = json.loads(result_text)
            return result
            
        except Exception as e:
            logger.error(f"뉴스 요약 처리 오류: {e}")
            return None
    
    async def generate_investment_strategy(self, 
                                         stock_name: str, 
                                         stock_code: str,
                                         current_price: float,
                                         portfolio_info: Dict,
                                         news_summaries: List[Dict],
                                         previous_strategy: Optional[str] = None) -> StrategyResult:
        """투자 전략 생성"""
        
        # 뉴스 요약 정보 정리
        news_summary_text = ""
        positive_news = []
        negative_news = []
        
        for news in news_summaries:
            sentiment = news.get('sentiment', 'NEUTRAL')
            summary = news.get('summary', '')
            
            if sentiment == 'POSITIVE':
                positive_news.append(summary)
            elif sentiment == 'NEGATIVE':
                negative_news.append(summary)
        
        news_summary_text = f"""
긍정적 뉴스 ({len(positive_news)}건):
{chr(10).join([f"- {news}" for news in positive_news[:5]])}

부정적 뉴스 ({len(negative_news)}건):
{chr(10).join([f"- {news}" for news in negative_news[:5]])}
"""

        prompt = f"""
당신은 전문 금융 분석가입니다. 다음 정보를 바탕으로 '{stock_name}({stock_code})' 종목에 대한 투자 전략을 제시해주세요.

== 종목 정보 ==
종목명: {stock_name}
종목코드: {stock_code}
현재가: {current_price:,}원

== 포트폴리오 정보 ==
보유수량: {portfolio_info.get('quantity', 0)}주
평균매입가: {portfolio_info.get('avg_price', 0):,}원
현재평가액: {portfolio_info.get('quantity', 0) * current_price:,}원
평가손익률: {((current_price - portfolio_info.get('avg_price', 0)) / portfolio_info.get('avg_price', 1) * 100):.2f}%

== 최근 뉴스 분석 ==
{news_summary_text}

== 이전 전략 ==
이전 전략: {previous_strategy or '없음'}

다음 JSON 형식으로 투자 전략을 제시해주세요:
{{
    "strategy_type": "BUY/SELL/HOLD 중 하나",
    "confidence": 0.0-1.0 사이의 신뢰도,
    "reasoning": "전략 선택 이유를 상세히 설명 (200자 이내)",
    "target_price": 목표가 (숫자, 선택사항),
    "sentiment": "POSITIVE/NEGATIVE/NEUTRAL",
    "risk_factors": ["리스크 요인1", "리스크 요인2"],
    "opportunity_factors": ["기회 요인1", "기회 요인2"]
}}

전략 결정 기준:
- BUY: 긍정적 뉴스가 많고, 기술적/재무적 지표가 상승을 시사할 때
- SELL: 부정적 뉴스가 많고, 하락 위험이 클 때  
- HOLD: 불확실성이 높거나 현재 상태 유지가 적절할 때

신뢰도는 분석의 확실성 정도를 나타냅니다 (0.7 이상이면 높은 신뢰도).
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON 파싱
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()
            
            result = json.loads(result_text)
            
            return StrategyResult(
                strategy_type=result.get('strategy_type', 'HOLD'),
                confidence=float(result.get('confidence', 0.5)),
                reasoning=result.get('reasoning', ''),
                target_price=result.get('target_price'),
                sentiment=result.get('sentiment', 'NEUTRAL')
            )
            
        except Exception as e:
            logger.error(f"투자 전략 생성 오류: {e}")
            # 기본 전략 반환
            return StrategyResult(
                strategy_type='HOLD',
                confidence=0.3,
                reasoning='분석 중 오류가 발생하여 관망 전략을 권장합니다.',
                sentiment='NEUTRAL'
            )
    
    async def analyze_market_sentiment(self, news_summaries: List[Dict]) -> Dict:
        """시장 전반적인 심리 분석"""
        
        if not news_summaries:
            return {
                'overall_sentiment': 'NEUTRAL',
                'confidence': 0.5,
                'summary': '분석할 뉴스가 없습니다.'
            }
        
        news_text = "\n".join([
            f"제목: {news.get('title', '')}\n요약: {news.get('summary', '')}"
            for news in news_summaries[:10]  # 최대 10개 뉴스만 분석
        ])
        
        prompt = f"""
다음은 최근 금융/경제 뉴스들입니다. 이를 바탕으로 전반적인 시장 심리를 분석해주세요.

뉴스 내용:
{news_text}

다음 JSON 형식으로 분석 결과를 제시해주세요:
{{
    "overall_sentiment": "POSITIVE/NEGATIVE/NEUTRAL",
    "confidence": 0.0-1.0,
    "summary": "시장 심리에 대한 간단한 요약 (100자 이내)",
    "key_themes": ["주요 테마1", "주요 테마2", "주요 테마3"]
}}
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()
            
            return json.loads(result_text)
            
        except Exception as e:
            logger.error(f"시장 심리 분석 오류: {e}")
            return {
                'overall_sentiment': 'NEUTRAL',
                'confidence': 0.5,
                'summary': '분석 중 오류가 발생했습니다.'
            }
