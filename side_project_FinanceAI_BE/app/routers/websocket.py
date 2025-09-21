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
