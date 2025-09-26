from typing import List, Dict, Optional
import asyncio
import json
import logging
from datetime import datetime
from fastapi import WebSocket
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        # WebSocket 연결 관리
        self.active_connections: Dict[int, List[WebSocket]] = {}  # user_id: [websocket_connections]
        
    async def connect(self, websocket: WebSocket, user_id: int):
        """WebSocket 연결 등록"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"사용자 {user_id} WebSocket 연결됨. 총 연결 수: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """WebSocket 연결 해제"""
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                logger.info(f"사용자 {user_id} WebSocket 연결 해제됨")
            except ValueError:
                pass
    
    async def send_strategy_change_notification(self, user_id: int, strategy_changes: List[Dict]):
        """전략 변경 알림 전송"""
        if user_id not in self.active_connections:
            logger.info(f"사용자 {user_id}의 활성 연결이 없습니다.")
            return
        
        notification = {
            "type": "STRATEGY_CHANGE",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "changes": strategy_changes,
                "total_changes": len(strategy_changes)
            }
        }
        
        # 연결된 모든 WebSocket에 전송
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
            except Exception as e:
                logger.error(f"WebSocket 전송 오류: {e}")
                disconnected_sockets.append(websocket)
        
        # 끊어진 연결 정리
        for socket in disconnected_sockets:
            self.disconnect(socket, user_id)
        
        logger.info(f"사용자 {user_id}에게 전략 변경 알림 전송 완료: {len(strategy_changes)}건")
    
    async def send_news_alert(self, user_id: int, news_data: Dict):
        """중요 뉴스 알림 전송"""
        if user_id not in self.active_connections:
            return
        
        notification = {
            "type": "NEWS_ALERT",
            "timestamp": datetime.utcnow().isoformat(),
            "data": news_data
        }
        
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
            except Exception as e:
                logger.error(f"WebSocket 전송 오류: {e}")
                disconnected_sockets.append(websocket)
        
        for socket in disconnected_sockets:
            self.disconnect(socket, user_id)
    
    async def send_market_alert(self, user_id: int, alert_data: Dict):
        """시장 상황 알림 전송"""
        if user_id not in self.active_connections:
            return
        
        notification = {
            "type": "MARKET_ALERT",
            "timestamp": datetime.utcnow().isoformat(),
            "data": alert_data
        }
        
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
            except Exception as e:
                logger.error(f"WebSocket 전송 오류: {e}")
                disconnected_sockets.append(websocket)
        
        for socket in disconnected_sockets:
            self.disconnect(socket, user_id)
    
    async def send_price_update_notification(self, user_id: int, updated_portfolios: List[Dict]):
        """주식 가격 업데이트 알림 전송"""
        if user_id not in self.active_connections:
            logger.info(f"사용자 {user_id}의 활성 연결이 없습니다.")
            return
        
        notification = {
            "type": "PRICE_UPDATE",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "portfolios": updated_portfolios,
                "total_updated": len(updated_portfolios)
            }
        }
        
        # 연결된 모든 WebSocket에 전송
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
            except Exception as e:
                logger.error(f"WebSocket 전송 오류: {e}")
                disconnected_sockets.append(websocket)
        
        # 끊어진 연결 정리
        for socket in disconnected_sockets:
            self.disconnect(socket, user_id)
        
        logger.info(f"사용자 {user_id}에게 가격 업데이트 알림 전송 완료: {len(updated_portfolios)}건")
    
    async def broadcast_system_message(self, message: str, message_type: str = "INFO"):
        """시스템 메시지 전체 사용자에게 브로드캐스트"""
        notification = {
            "type": "SYSTEM_MESSAGE",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "message": message,
                "message_type": message_type
            }
        }
        
        for user_id, connections in self.active_connections.items():
            disconnected_sockets = []
            for websocket in connections:
                try:
                    await websocket.send_text(json.dumps(notification, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"시스템 메시지 전송 오류 (사용자 {user_id}): {e}")
                    disconnected_sockets.append(websocket)
            
            for socket in disconnected_sockets:
                self.disconnect(socket, user_id)
    
    def get_connected_users(self) -> List[int]:
        """현재 연결된 사용자 ID 목록 반환"""
        return list(self.active_connections.keys())
    
    def get_connection_count(self, user_id: int = None) -> int:
        """연결 수 반환 (특정 사용자 또는 전체)"""
        if user_id:
            return len(self.active_connections.get(user_id, []))
        return sum(len(connections) for connections in self.active_connections.values())
    
    async def send_notification_to_user(self, user_id: int, notification: Dict):
        """특정 사용자에게 알림 전송"""
        if user_id not in self.active_connections:
            logger.info(f"사용자 {user_id}의 활성 연결이 없습니다.")
            return
        
        # 알림에 타임스탬프 추가
        notification["timestamp"] = datetime.utcnow().isoformat()
        
        # 연결된 모든 WebSocket에 전송
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
            except Exception as e:
                logger.error(f"WebSocket 전송 오류: {e}")
                disconnected_sockets.append(websocket)
        
        # 끊어진 연결 정리
        for socket in disconnected_sockets:
            self.disconnect(socket, user_id)
        
        logger.info(f"사용자 {user_id}에게 알림 전송 완료: {notification.get('type', 'UNKNOWN')}")

# 전역 알림 매니저 인스턴스
notification_manager = NotificationManager()

class NotificationService:
    def __init__(self):
        self.manager = notification_manager
    
    async def process_strategy_changes(self, user_id: int, strategy_changes: List[Dict]):
        """전략 변경 처리 및 알림"""
        
        # 중요한 변경사항만 필터링
        important_changes = []
        for change in strategy_changes:
            if change['changed'] and change['confidence'] >= 0.7:
                important_changes.append({
                    'stock_name': change['stock_name'],
                    'stock_code': change['stock_code'],
                    'previous_strategy': change['previous_strategy'],
                    'new_strategy': change['new_strategy'],
                    'confidence': change['confidence'],
                    'reasoning': change['reasoning'][:100] + '...' if len(change['reasoning']) > 100 else change['reasoning']
                })
        
        if important_changes:
            await self.manager.send_strategy_change_notification(user_id, important_changes)
    
    async def process_high_impact_news(self, user_id: int, portfolio_id: int, news_data: Dict):
        """고영향 뉴스 처리 및 알림"""
        
        # 높은 관련도 또는 강한 감정의 뉴스만 알림
        if news_data.get('relevance_score', 0) >= 0.8 or news_data.get('sentiment') in ['VERY_POSITIVE', 'VERY_NEGATIVE']:
            alert_data = {
                'portfolio_id': portfolio_id,
                'title': news_data['title'],
                'summary': news_data['summary'],
                'sentiment': news_data['sentiment'],
                'relevance_score': news_data['relevance_score'],
                'published_at': news_data['published_at']
            }
            
            await self.manager.send_news_alert(user_id, alert_data)
    
    async def check_market_conditions(self, user_id: int, market_data: Dict):
        """시장 상황 체크 및 알림"""
        
        # 급격한 시장 변화 감지
        if market_data.get('volatility', 0) > 0.05:  # 5% 이상 변동성
            alert_data = {
                'alert_type': 'HIGH_VOLATILITY',
                'message': f"시장 변동성이 높습니다 ({market_data['volatility']*100:.1f}%)",
                'recommendations': market_data.get('recommendations', [])
            }
            
            await self.manager.send_market_alert(user_id, alert_data)
    
    async def send_daily_summary(self, user_id: int, summary_data: Dict):
        """일일 요약 알림"""
        
        notification = {
            "type": "DAILY_SUMMARY",
            "timestamp": datetime.utcnow().isoformat(),
            "data": summary_data
        }
        
        if user_id in self.manager.active_connections:
            disconnected_sockets = []
            for websocket in self.manager.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(notification, ensure_ascii=False))
                except Exception as e:
                    logger.error(f"일일 요약 전송 오류: {e}")
                    disconnected_sockets.append(websocket)
            
            for socket in disconnected_sockets:
                self.manager.disconnect(socket, user_id)

# 전역 알림 서비스 인스턴스
notification_service = NotificationService()
