# 🚀 Finance AI 빠른 시작 가이드

## 1. 필수 요구사항
- Python 3.8 이상
- Gemini API 키 (Google AI Studio에서 발급)
- 공공데이터 포털 주식 API 키 (data.go.kr에서 발급)

## 2. 설치 및 설정

### 2.1 의존성 설치
```bash
cd side_project_FinanceAI_BE
pip install -r requirements.txt
```

### 2.2 API 키 설정

#### Gemini API 키
1. [Google AI Studio](https://makersuite.google.com/app/apikey)에서 Gemini API 키 발급
2. `.env` 파일에서 `GEMINI_API_KEY=your_actual_api_key` 설정

#### 주식 시세 API 키
1. [공공데이터 포털](https://www.data.go.kr/)에서 회원가입
2. "한국투자증권_국내주식시세" 서비스 신청 및 승인
3. `.env` 파일에서 `STOCK_API_KEY=your_actual_api_key` 설정

### 2.3 데모 데이터 생성
```bash
cd side_project_FinanceAI_BE
python create_demo_data.py
```

## 3. 서버 실행

### 방법 1: 자동 스크립트 사용
```bash
python start_server.py
```

### 방법 2: 직접 실행
```bash
cd side_project_FinanceAI_BE
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 4. 프론트엔드 접속
- `side_project_FinanceAI_FE/index.html` 파일을 브라우저에서 열기
- Live Server 사용 시: http://localhost:3000

## 5. 기능 테스트

### 5.1 WebSocket 연결 확인
- 프론트엔드 접속 시 "서버에 연결되었습니다" 알림 확인

### 5.2 전략 업데이트 테스트
1. API 문서 접속: http://localhost:8000/docs
2. `POST /api/portfolio/update-strategies` 실행
3. 프론트엔드에서 실시간 알림 확인

### 5.3 가격 업데이트 테스트
1. 프론트엔드 우측 하단 원형 버튼 클릭
2. `POST /api/portfolio/update-prices` API 호출
3. 실시간 가격 변화 애니메이션 확인

### 5.4 포트폴리오 관리
- 프론트엔드에서 "+" 버튼으로 새 종목 추가
- 기존 종목 클릭하여 상세 정보 확인
- 실시간 가격 변화 및 수익률 확인

## 6. 주요 URL
- 🏠 메인 서버: http://localhost:8000
- 📚 API 문서: http://localhost:8000/docs
- 🔍 Alternative 문서: http://localhost:8000/redoc
- 💓 헬스 체크: http://localhost:8000/health

## 7. 문제 해결

### API 키 오류
```
❌ Gemini API 키가 설정되지 않았습니다
❌ 공공데이터 포털 API 키가 설정되지 않았습니다
```
→ `.env` 파일에서 `GEMINI_API_KEY`, `STOCK_API_KEY` 확인

### WebSocket 연결 실패
```
❌ 서버 연결에 실패했습니다
```
→ 백엔드 서버가 실행 중인지 확인 (http://localhost:8000/health)

### 뉴스 크롤링 실패
```
❌ 뉴스 크롤링 오류
```
→ 네트워크 연결 및 사이트 접근 가능 여부 확인

### 주식 가격 조회 실패
```
❌ 주식 가격 조회 오류
```
→ 공공데이터 포털 API 키 및 서비스 승인 상태 확인

## 8. 개발자 모드

### 로그 레벨 변경
```bash
# .env 파일에서
LOG_LEVEL=DEBUG
```

### 데이터베이스 초기화
```bash
rm finance_ai.db
python create_demo_data.py
```

### API 테스트
```bash
# 포트폴리오 조회
curl http://localhost:8000/api/portfolio/

# 전략 업데이트
curl -X POST http://localhost:8000/api/portfolio/update-strategies

# 가격 업데이트
curl -X POST http://localhost:8000/api/portfolio/update-prices

# 시장 요약
curl http://localhost:8000/api/portfolio/market-summary
```

## 9. 다음 단계
- 실제 종목 데이터로 포트폴리오 구성
- 커스텀 키워드 추가로 뉴스 필터링 최적화
- 전략 변경 알림 설정 조정

---

**💡 팁**: 처음 실행 시 뉴스 크롤링과 AI 분석에 시간이 걸릴 수 있습니다. 인내심을 갖고 기다려주세요!
