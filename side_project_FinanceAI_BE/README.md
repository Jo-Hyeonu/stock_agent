# Finance AI - 포트폴리오 기반 뉴스 분석 및 투자 전략 시스템

AI 기반 금융 포트폴리오 관리 시스템으로, 사용자의 포트폴리오 종목 관련 뉴스를 자동으로 크롤링하고 Gemini 2.5 Flash를 활용해 분석하여 투자 전략을 제공합니다.

## 주요 기능

### 🔍 뉴스 크롤링
- 포트폴리오 종목별 맞춤 키워드 기반 뉴스 수집
- 네이버뉴스, 다음뉴스 등 주요 포털 크롤링
- 뉴스 관련도 점수 계산 및 필터링

### 📈 실시간 주식 시세
- 공공데이터 포털 주식 시세 API 연동
- 실시간 가격 업데이트 및 수익률 계산
- 장중/장마감 상태 자동 감지
- 가격 변화 시각적 표시

### 🤖 AI 분석
- Gemini 2.5 Flash API를 활용한 뉴스 요약
- 감정 분석 및 종목 영향도 평가
- 포트폴리오별 맞춤 투자 전략 생성 (매수/매도/관망)

### 📱 실시간 알림
- WebSocket 기반 실시간 전략 변경 알림
- 중요 뉴스 및 시장 상황 알림
- 프론트엔드 푸시 알림 시스템

### 📊 포트폴리오 관리
- 종목 추가/수정/삭제
- 전략 히스토리 추적
- 뉴스 요약 통계

## 기술 스택

### Backend
- **FastAPI**: 고성능 API 서버
- **SQLAlchemy**: ORM 및 데이터베이스 관리
- **SQLite**: 경량 데이터베이스
- **WebSocket**: 실시간 통신
- **Gemini 2.5 Flash**: AI 분석 엔진
- **httpx + BeautifulSoup**: 뉴스 크롤링

### Frontend
- **HTML5 + Tailwind CSS**: 모던 UI
- **Vanilla JavaScript**: 경량 프론트엔드
- **WebSocket API**: 실시간 알림

## 설치 및 실행

### 1. 환경 설정

```bash
cd side_project_FinanceAI_BE

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
# .env 파일 편집
# 다음 API 키들을 설정해주세요
```

### 3. API 키 발급

#### Gemini API 키 (필수)
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 방문
2. API 키 생성
3. `.env` 파일에 `GEMINI_API_KEY` 설정

#### 공공데이터 포털 주식 API 키 (필수)
1. [공공데이터 포털](https://www.data.go.kr/) 회원가입
2. "한국투자증권_국내주식시세" 서비스 신청
3. 승인 후 API 키 발급
4. `.env` 파일에 `STOCK_API_KEY` 설정

### 4. 서버 실행

```bash
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 프론트엔드 접속
- 브라우저에서 `side_project_FinanceAI_FE/index.html` 파일 열기
- 또는 Live Server 등을 사용하여 `http://localhost:3000` 에서 실행

## API 문서

서버 실행 후 다음 URL에서 API 문서 확인:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 API 엔드포인트

### 포트폴리오 관리
- `GET /api/portfolio/` - 포트폴리오 목록 조회
- `POST /api/portfolio/` - 종목 추가
- `PUT /api/portfolio/{id}` - 종목 수정
- `DELETE /api/portfolio/{id}` - 종목 삭제

### 전략 관리
- `POST /api/portfolio/update-strategies` - 전략 업데이트
- `GET /api/portfolio/{id}/strategies` - 전략 히스토리
- `GET /api/portfolio/{id}/news-summary` - 뉴스 요약

### 주식 가격 관리
- `POST /api/portfolio/update-prices` - 가격 업데이트
- `GET /api/portfolio/{id}/price-info` - 종목별 상세 가격 정보
- `GET /api/portfolio/market-summary` - 시장 요약
- `GET /api/portfolio/price-status` - 가격 업데이트 상태

### WebSocket
- `WS /ws/{user_id}` - 실시간 알림 연결

## 사용 방법

### 1. 포트폴리오 설정
1. 프론트엔드에서 "+" 버튼 클릭
2. 보유 종목 추가 (종목명, 수량, 평균매입가)

### 2. 전략 업데이트
1. 대시보드에서 자동 업데이트 대기 또는
2. 수동으로 "전략 재분석" 버튼 클릭

### 3. 실시간 가격 업데이트
1. 우측 하단 원형 버튼 클릭으로 수동 업데이트 또는
2. 장중 시간에 자동으로 5분마다 업데이트

### 4. 실시간 알림 확인
- WebSocket 연결 시 자동으로 전략 변경 알림 수신
- 가격 변화 시 실시간 알림 및 시각적 효과
- 중요 뉴스 및 시장 상황 알림 확인

## 커스터마이징

### 뉴스 크롤링 키워드 추가
```python
# API 호출로 커스텀 키워드 추가
POST /api/portfolio/{id}/keywords
{
    "keyword": "실적발표",
    "priority": 1
}
```

### 전략 업데이트 주기 변경
```python
# .env 파일에서 설정
STRATEGY_UPDATE_INTERVAL_MINUTES=120  # 2시간마다
NEWS_CRAWL_INTERVAL_MINUTES=60        # 1시간마다
```

## 주의사항

1. **API 키 필수**: 
   - Gemini API 키: AI 분석 기능
   - 공공데이터 포털 API 키: 실시간 주식 시세
2. **크롤링 제한**: 과도한 크롤링으로 인한 IP 차단 방지를 위해 적절한 딜레이 설정
3. **데이터 정확성**: 뉴스 크롤링 및 주식 시세의 정확성은 소스에 의존
4. **장 시간 확인**: 실시간 가격 업데이트는 장중 시간(09:00-15:30)에만 유효
5. **투자 책임**: AI 분석 결과는 참고용이며, 최종 투자 결정은 사용자 책임

## 개발 로드맵

- [ ] 더 많은 뉴스 소스 추가
- [ ] 기술적 지표 분석 통합
- [ ] 사용자 인증 시스템
- [ ] 모바일 앱 개발
- [ ] 백테스팅 기능
- [ ] 소셜 트레이딩 기능

## 라이선스

MIT License

## 문의

프로젝트 관련 문의사항이 있으시면 이슈를 등록해 주세요.
