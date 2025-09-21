import httpx
from bs4 import BeautifulSoup
from typing import List, Dict
import asyncio
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)

class NewsSource:
    def __init__(self, name: str, base_url: str, search_path: str):
        self.name = name
        self.base_url = base_url
        self.search_path = search_path

class NewsCrawler:
    def __init__(self):
        self.sources = [
            NewsSource(
                "네이버뉴스", 
                "https://search.naver.com",
                "/search.naver?where=news&query={keyword}&sort=1"
            ),
            NewsSource(
                "다음뉴스",
                "https://search.daum.net", 
                "/search?w=news&q={keyword}&sort=recency"
            )
        ]
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def crawl_naver_news(self, keyword: str, max_articles: int = 10) -> List[Dict]:
        """네이버 뉴스 크롤링"""
        articles = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                search_url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1"
                response = await client.get(search_url, headers=self.headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    news_items = soup.select('.news_area')
                    
                    for item in news_items[:max_articles]:
                        try:
                            title_elem = item.select_one('.news_tit')
                            if not title_elem:
                                continue
                                
                            title = title_elem.get_text().strip()
                            url = title_elem.get('href', '')
                            
                            # 뉴스 내용 미리보기
                            content_elem = item.select_one('.news_dsc')
                            content = content_elem.get_text().strip() if content_elem else ""
                            
                            # 발행일시
                            date_elem = item.select_one('.info_group .info')
                            date_str = date_elem.get_text().strip() if date_elem else ""
                            published_at = self._parse_date(date_str)
                            
                            # 언론사
                            press_elem = item.select_one('.press')
                            press = press_elem.get_text().strip() if press_elem else ""
                            
                            if title and url:
                                articles.append({
                                    'title': title,
                                    'url': url,
                                    'content': content,
                                    'published_at': published_at,
                                    'press': press,
                                    'source': 'naver'
                                })
                        except Exception as e:
                            logger.warning(f"네이버 뉴스 항목 파싱 오류: {e}")
                            continue
                            
        except Exception as e:
            logger.error(f"네이버 뉴스 크롤링 오류: {e}")
            
        return articles
    
    async def crawl_daum_news(self, keyword: str, max_articles: int = 10) -> List[Dict]:
        """다음 뉴스 크롤링"""
        articles = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                search_url = f"https://search.daum.net/search?w=news&q={keyword}&sort=recency"
                response = await client.get(search_url, headers=self.headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    news_items = soup.select('.item-news')
                    
                    for item in news_items[:max_articles]:
                        try:
                            title_elem = item.select_one('.tit-news a')
                            if not title_elem:
                                continue
                                
                            title = title_elem.get_text().strip()
                            url = title_elem.get('href', '')
                            
                            # 뉴스 내용 미리보기
                            content_elem = item.select_one('.desc')
                            content = content_elem.get_text().strip() if content_elem else ""
                            
                            # 발행일시
                            date_elem = item.select_one('.info-news .txt-date')
                            date_str = date_elem.get_text().strip() if date_elem else ""
                            published_at = self._parse_date(date_str)
                            
                            # 언론사
                            press_elem = item.select_one('.info-news .txt-cp')
                            press = press_elem.get_text().strip() if press_elem else ""
                            
                            if title and url:
                                articles.append({
                                    'title': title,
                                    'url': url,
                                    'content': content,
                                    'published_at': published_at,
                                    'press': press,
                                    'source': 'daum'
                                })
                        except Exception as e:
                            logger.warning(f"다음 뉴스 항목 파싱 오류: {e}")
                            continue
                            
        except Exception as e:
            logger.error(f"다음 뉴스 크롤링 오류: {e}")
            
        return articles
    
    async def get_full_article_content(self, url: str) -> str:
        """뉴스 전문 가져오기"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 네이버 뉴스 본문 추출
                    if 'news.naver.com' in url:
                        content_elem = soup.select_one('#dic_area, .go_trans._article_content')
                        if content_elem:
                            return content_elem.get_text().strip()
                    
                    # 다음 뉴스 본문 추출
                    elif 'news.daum.net' in url:
                        content_elem = soup.select_one('.article_view section p')
                        if content_elem:
                            return content_elem.get_text().strip()
                    
                    # 일반적인 본문 추출 시도
                    for selector in ['.article-body', '.news-content', '.content', 'article']:
                        content_elem = soup.select_one(selector)
                        if content_elem:
                            return content_elem.get_text().strip()
                            
        except Exception as e:
            logger.warning(f"뉴스 본문 가져오기 오류 ({url}): {e}")
            
        return ""
    
    async def crawl_news_for_keywords(self, keywords: List[str], max_articles_per_keyword: int = 5) -> List[Dict]:
        """키워드별 뉴스 크롤링"""
        all_articles = []
        
        for keyword in keywords:
            logger.info(f"키워드 '{keyword}'에 대한 뉴스 크롤링 시작")
            
            # 네이버와 다음 뉴스를 병렬로 크롤링
            tasks = [
                self.crawl_naver_news(keyword, max_articles_per_keyword),
                self.crawl_daum_news(keyword, max_articles_per_keyword)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    for article in result:
                        article['keyword'] = keyword
                        all_articles.append(article)
        
        # 중복 제거 (URL 기준)
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        # 최신순 정렬
        unique_articles.sort(key=lambda x: x['published_at'], reverse=True)
        
        logger.info(f"총 {len(unique_articles)}개의 뉴스 기사를 수집했습니다")
        return unique_articles
    
    def _parse_date(self, date_str: str) -> datetime:
        """날짜 문자열을 datetime 객체로 변환"""
        try:
            # "2시간 전", "1일 전" 형태 처리
            if '시간 전' in date_str:
                hours = int(re.findall(r'(\d+)시간 전', date_str)[0])
                return datetime.now() - timedelta(hours=hours)
            elif '일 전' in date_str:
                days = int(re.findall(r'(\d+)일 전', date_str)[0])
                return datetime.now() - timedelta(days=days)
            elif '분 전' in date_str:
                minutes = int(re.findall(r'(\d+)분 전', date_str)[0])
                return datetime.now() - timedelta(minutes=minutes)
            elif '방금' in date_str or '초 전' in date_str:
                return datetime.now()
            else:
                # 기본값으로 현재 시간 반환
                return datetime.now()
        except:
            return datetime.now()
    
    def calculate_relevance_score(self, article: Dict, target_keywords: List[str]) -> float:
        """뉴스 기사의 관련도 점수 계산"""
        title = article.get('title', '').lower()
        content = article.get('content', '').lower()
        
        score = 0.0
        total_keywords = len(target_keywords)
        
        for keyword in target_keywords:
            keyword_lower = keyword.lower()
            
            # 제목에서 키워드 발견 시 높은 점수
            if keyword_lower in title:
                score += 0.6
            
            # 내용에서 키워드 발견 시 중간 점수
            if keyword_lower in content:
                score += 0.4
        
        # 정규화 (0-1 범위)
        return min(score / total_keywords, 1.0) if total_keywords > 0 else 0.0
