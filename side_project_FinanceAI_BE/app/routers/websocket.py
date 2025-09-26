from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json
import logging
from typing import Dict, Any

from ..db.database import get_db
from ..services.notification_service import notification_manager
from ..services.strategy_service import StrategyService
from ..core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

def get_strategy_service():
    settings = get_settings()
    return StrategyService(settings.GEMINI_API_KEY)

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket 연결 엔드포인트"""
    
    await notification_manager.connect(websocket, user_id)
    
    try:
        # 연결 확인 메시지 전송
        await websocket.send_text(json.dumps({
            "type": "CONNECTION_ESTABLISHED",
            "message": f"사용자 {user_id} WebSocket 연결됨",
            "user_id": user_id
        }, ensure_ascii=False))
        
        # 최근 전략 변경 내역 전송 (옵션)
        strategy_service = get_strategy_service()
        recent_changes = await strategy_service.get_strategy_changes(db, user_id, hours=24)
        
        if recent_changes:
            await websocket.send_text(json.dumps({
                "type": "RECENT_STRATEGY_CHANGES",
                "data": {
                    "changes": recent_changes,
                    "count": len(recent_changes)
                }
            }, ensure_ascii=False))
        
        # 클라이언트 메시지 수신 대기
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                await handle_websocket_message(websocket, user_id, message, db)
                
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "ERROR",
                    "message": "잘못된 JSON 형식입니다."
                }, ensure_ascii=False))
                
    except WebSocketDisconnect:
        notification_manager.disconnect(websocket, user_id)
        logger.info(f"사용자 {user_id} WebSocket 연결 해제")
        
    except Exception as e:
        logger.error(f"WebSocket 오류 (사용자 {user_id}): {e}")
        notification_manager.disconnect(websocket, user_id)

async def handle_websocket_message(
    websocket: WebSocket, 
    user_id: int, 
    message: Dict[str, Any],
    db: Session
):
    """WebSocket 메시지 처리"""
    
    message_type = message.get("type")
    
    try:
        if message_type == "PING":
            # Ping-Pong for keep-alive
            await websocket.send_text(json.dumps({
                "type": "PONG",
                "timestamp": message.get("timestamp")
            }, ensure_ascii=False))
            
        elif message_type == "REQUEST_STRATEGY_UPDATE":
            # 전략 업데이트 요청
            portfolio_id = message.get("portfolio_id")
            
            if portfolio_id:
                await websocket.send_text(json.dumps({
                    "type": "STRATEGY_UPDATE_STARTED",
                    "portfolio_id": portfolio_id,
                    "message": "전략 업데이트를 시작합니다."
                }, ensure_ascii=False))
                
                # 백그라운드에서 전략 업데이트 실행
                # (실제 구현에서는 Celery 등을 사용하는 것이 좋습니다)
                
            else:
                await websocket.send_text(json.dumps({
                    "type": "ERROR",
                    "message": "portfolio_id가 필요합니다."
                }, ensure_ascii=False))
                
        elif message_type == "REQUEST_NEWS_SUMMARY":
            # 뉴스 요약 요청
            portfolio_id = message.get("portfolio_id")
            days = message.get("days", 7)
            
            if portfolio_id:
                strategy_service = get_strategy_service()
                news_summary = await strategy_service.get_portfolio_news_summary(db, portfolio_id, days)
                
                await websocket.send_text(json.dumps({
                    "type": "NEWS_SUMMARY",
                    "portfolio_id": portfolio_id,
                    "data": news_summary
                }, ensure_ascii=False))
                
        elif message_type == "SUBSCRIBE_NOTIFICATIONS":
            # 알림 구독 설정
            notification_types = message.get("types", ["STRATEGY_CHANGE", "NEWS_ALERT"])
            
            await websocket.send_text(json.dumps({
                "type": "SUBSCRIPTION_CONFIRMED",
                "subscribed_types": notification_types,
                "message": "알림 구독이 설정되었습니다."
            }, ensure_ascii=False))
            
        else:
            await websocket.send_text(json.dumps({
                "type": "ERROR",
                "message": f"알 수 없는 메시지 타입: {message_type}"
            }, ensure_ascii=False))
            
    except Exception as e:
        logger.error(f"메시지 처리 오류 (사용자 {user_id}, 타입 {message_type}): {e}")
        await websocket.send_text(json.dumps({
            "type": "ERROR",
            "message": "메시지 처리 중 오류가 발생했습니다."
        }, ensure_ascii=False))

@router.get("/ws/status")
async def websocket_status():
    """WebSocket 연결 상태 조회"""
    
    connected_users = notification_manager.get_connected_users()
    total_connections = notification_manager.get_connection_count()
    
    return {
        "connected_users": connected_users,
        "total_connections": total_connections,
        "user_connections": {
            user_id: notification_manager.get_connection_count(user_id) 
            for user_id in connected_users
        }
    }

@router.post("/ws/broadcast")
async def broadcast_message(
    message: str,
    message_type: str = "INFO"
):
    """시스템 메시지 브로드캐스트 (관리자용)"""
    
    await notification_manager.broadcast_system_message(message, message_type)
    
    return {
        "message": "메시지가 모든 연결된 사용자에게 전송되었습니다.",
        "recipients": len(notification_manager.get_connected_users())
    }

@router.post("/ws/test-strategy-notification/{user_id}")
async def test_strategy_notification(user_id: int):
    """전략 변경 알림 테스트용 엔드포인트"""
    
    # 테스트용 전략 변경 알림 데이터
    test_notification = {
        "type": "STRATEGY_CHANGE",
        "title": "포트폴리오 전략이 업데이트되었습니다",
        "message": "AI가 새로운 투자 전략을 분석하여 포트폴리오를 최적화했습니다.",
        "portfolio_id": 1,
        "portfolio_name": "테스트 포트폴리오",
        "changes": [
            {
                "stock_name": "삼성전자",
                "action": "매수",
                "reason": "기술적 분석 결과 상승 추세 확인",
                "confidence": 85
            },
            {
                "stock_name": "SK하이닉스",
                "action": "매도",
                "reason": "시장 변동성 증가로 리스크 관리",
                "confidence": 78
            }
        ],
        "timestamp": "2025-09-26T20:52:00Z",
        "priority": "high"
    }
    
    # 특정 사용자에게 알림 전송
    await notification_manager.send_notification_to_user(user_id, test_notification)
    
    return {
        "message": f"사용자 {user_id}에게 전략 변경 알림이 전송되었습니다.",
        "notification": test_notification
    }

@router.post("/ws/test-all-notifications")
async def test_all_notifications():
    """모든 연결된 사용자에게 테스트 알림 전송"""
    
    test_notifications = [
        {
            "type": "STRATEGY_CHANGE",
            "title": "포트폴리오 전략 업데이트",
            "message": "새로운 AI 분석 결과가 반영되었습니다.",
            "priority": "high"
        },
        {
            "type": "NEWS_ALERT",
            "title": "중요 뉴스 알림",
            "message": "관심 종목에 대한 중요한 뉴스가 있습니다.",
            "priority": "medium"
        },
        {
            "type": "PRICE_ALERT",
            "title": "가격 변동 알림",
            "message": "포트폴리오 종목의 급격한 가격 변동이 감지되었습니다.",
            "priority": "high"
        }
    ]
    
    connected_users = notification_manager.get_connected_users()
    sent_count = 0
    
    for user_id in connected_users:
        for notification in test_notifications:
            await notification_manager.send_notification_to_user(user_id, notification)
            sent_count += 1
    
    return {
        "message": f"{len(connected_users)}명의 사용자에게 {sent_count}개의 테스트 알림이 전송되었습니다.",
        "connected_users": connected_users,
        "notifications_sent": sent_count
    }
