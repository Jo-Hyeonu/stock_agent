#!/usr/bin/env python3
"""
데모 데이터 생성 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, create_tables
from app.models.user import User
from app.models.portfolio import Portfolio, NewsKeyword
from datetime import datetime

def create_demo_data():
    """데모용 사용자 및 포트폴리오 데이터 생성"""
    
    # 데이터베이스 테이블 생성
    create_tables()
    
    db = SessionLocal()
    
    try:
        # 기존 데모 사용자 확인
        demo_user = db.query(User).filter(User.email == "demo@financeai.com").first()
        
        if not demo_user:
            # 데모 사용자 생성
            demo_user = User(
                email="demo@financeai.com",
                name="데모 사용자"
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)
            print("✅ 데모 사용자가 생성되었습니다.")
        else:
            print("✅ 데모 사용자가 이미 존재합니다.")
        
        # 포트폴리오 데이터 생성
        demo_portfolios = [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 62,
                "avg_price": 82600,
                "current_price": 82600
            },
            {
                "stock_code": "000660", 
                "stock_name": "SK하이닉스",
                "quantity": 24,
                "avg_price": 131000,
                "current_price": 131000
            },
            {
                "stock_code": "035420",
                "stock_name": "NAVER",
                "quantity": 9,
                "avg_price": 298000,
                "current_price": 298000
            },
            {
                "stock_code": "035720",
                "stock_name": "카카오",
                "quantity": 12,
                "avg_price": 121500,
                "current_price": 121500
            },
            {
                "stock_code": "005380",
                "stock_name": "현대차",
                "quantity": 5,
                "avg_price": 228000,
                "current_price": 228000
            }
        ]
        
        for portfolio_data in demo_portfolios:
            existing = db.query(Portfolio).filter(
                Portfolio.user_id == demo_user.id,
                Portfolio.stock_code == portfolio_data["stock_code"]
            ).first()
            
            if not existing:
                portfolio = Portfolio(
                    user_id=demo_user.id,
                    **portfolio_data
                )
                db.add(portfolio)
                print(f"✅ {portfolio_data['stock_name']} 포트폴리오가 추가되었습니다.")
            else:
                print(f"✅ {portfolio_data['stock_name']} 포트폴리오가 이미 존재합니다.")
        
        db.commit()
        
        # 커스텀 키워드 추가
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == demo_user.id).all()
        
        for portfolio in portfolios:
            # 기본 키워드들 추가
            keywords = [
                f"{portfolio.stock_name} 실적",
                f"{portfolio.stock_name} 전망",
                f"{portfolio.stock_name} 분석"
            ]
            
            for keyword in keywords:
                existing_keyword = db.query(NewsKeyword).filter(
                    NewsKeyword.portfolio_id == portfolio.id,
                    NewsKeyword.keyword == keyword
                ).first()
                
                if not existing_keyword:
                    news_keyword = NewsKeyword(
                        portfolio_id=portfolio.id,
                        keyword=keyword,
                        priority=1
                    )
                    db.add(news_keyword)
        
        db.commit()
        
        print("\n🎉 데모 데이터 생성이 완료되었습니다!")
        print("👤 데모 사용자 ID: 1")
        print("📊 포트폴리오: 5개 종목")
        print("🔍 검색 키워드: 15개")
        print("\n서버를 시작하여 테스트해보세요!")
        
    except Exception as e:
        print(f"❌ 데모 데이터 생성 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_demo_data()
