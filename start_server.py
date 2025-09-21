#!/usr/bin/env python3
"""
Finance AI 서버 실행 스크립트
"""
import subprocess
import sys
import os
from dotenv import load_dotenv

load_dotenv()



def check_requirements():
    """필요한 패키지가 설치되어 있는지 확인"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import google.generativeai
        import httpx
        import beautifulsoup4
        print("✅ 모든 필수 패키지가 설치되어 있습니다.")
        return True
    except ImportError as e:
        print(f"❌ 필수 패키지가 누락되었습니다: {e}")
        print("다음 명령어로 설치하세요: pip install -r requirements.txt")
        return False

def check_env_file():
    """환경 설정 파일 확인"""
    env_path = "side_project_FinanceAI_BE/.env"
    if not os.path.exists(env_path):
        print(f"❌ 환경 설정 파일이 없습니다: {env_path}")
        print("README.md를 참고하여 .env 파일을 생성하세요.")
        return False
    
    with open(env_path, 'r') as f:
        content = f.read()
        if "your_gemini_api_key_here" in content:
            print("⚠️  Gemini API 키를 설정해주세요!")
            print("Google AI Studio에서 API 키를 발급받아 .env 파일에 설정하세요.")
            return False
    
    print("✅ 환경 설정 파일이 올바르게 구성되어 있습니다.")
    return True

def main():
    print("🚀 Finance AI 서버를 시작합니다...")
    
    # 필수 조건 확인
    if not check_requirements():
        sys.exit(1)
    
    if not check_env_file():
        sys.exit(1)
    
    # 서버 실행
    try:
        print("📡 FastAPI 서버를 시작합니다...")
        print("🌐 서버 주소: http://localhost:8000")
        print("📚 API 문서: http://localhost:8000/docs")
        print("🛑 서버를 중지하려면 Ctrl+C를 누르세요.")
        print("-" * 50)
        
        # 백엔드 디렉토리로 이동하여 서버 실행
        os.chdir("side_project_FinanceAI_BE")
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--reload", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ])
        
    except KeyboardInterrupt:
        print("\n🛑 서버가 중지되었습니다.")
    except Exception as e:
        print(f"❌ 서버 실행 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
