"""
WebSocket Task Manager

Provides real-time communication capabilities for task monitoring and management.
Integrates with the existing TaskManager to broadcast task status updates.
"""

import datetime
import json
from typing import Dict, Any, Optional
from flask_socketio import SocketIO, emit, join_room, leave_room
import colorlog

logger = colorlog.getLogger()


class WebSocketTaskManager:
    """
    WebSocket-enabled task manager for real-time communication.
    
    This class extends the existing TaskManager functionality with WebSocket
    support for broadcasting real-time task updates to connected clients.
    """
    
    def __init__(self, socketio: SocketIO, task_manager):
        """
        Initialize WebSocket Task Manager.
        
        Args:
            socketio: Flask-SocketIO instance
            task_manager: Existing TaskManager instance
        """
        self.socketio = socketio
        self.task_manager = task_manager
        self.connected_clients = {}
        self.client_subscriptions = {}
        
        # Register WebSocket event handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            client_id = self._get_client_id()
            self.connected_clients[client_id] = {
                'connected_at': datetime.datetime.now().isoformat(),
                'subscriptions': []
            }
            logger.info(f"Client {client_id} connected to WebSocket")
            emit('connection_status', {'status': 'connected', 'client_id': client_id})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            client_id = self._get_client_id()
            if client_id in self.connected_clients:
                # Leave all subscribed rooms
                subscriptions = self.connected_clients[client_id].get('subscriptions', [])
                for config_name in subscriptions:
                    leave_room(f"task_{config_name}")
                
                del self.connected_clients[client_id]
                logger.info(f"Client {client_id} disconnected from WebSocket")
        
        @self.socketio.on('subscribe_task')
        def handle_subscribe_task(data):
            """
            Handle task subscription request.
            
            Args:
                data: Dictionary containing 'config_name' to subscribe to
            """
            client_id = self._get_client_id()
            config_name = data.get('config_name')
            
            if not config_name:
                emit('error', {'message': 'config_name is required'})
                return
            
            # Validate config exists
            if config_name not in self.task_manager.profile:
                self.task_manager.register_profile(config_name)
            
            # Join room for this config
            join_room(f"task_{config_name}")
            
            # Track subscription
            if client_id in self.connected_clients:
                if config_name not in self.connected_clients[client_id]['subscriptions']:
                    self.connected_clients[client_id]['subscriptions'].append(config_name)
            
            # Send current task status
            current_status = self.task_manager.profile.get(config_name, {})
            emit('task_status', {
                'config_name': config_name,
                'status': current_status
            })
            
            logger.info(f"Client {client_id} subscribed to task updates for {config_name}")
        
        @self.socketio.on('unsubscribe_task')
        def handle_unsubscribe_task(data):
            """
            Handle task unsubscription request.
            
            Args:
                data: Dictionary containing 'config_name' to unsubscribe from
            """
            client_id = self._get_client_id()
            config_name = data.get('config_name')
            
            if not config_name:
                emit('error', {'message': 'config_name is required'})
                return
            
            # Leave room
            leave_room(f"task_{config_name}")
            
            # Remove from subscription tracking
            if client_id in self.connected_clients:
                subscriptions = self.connected_clients[client_id]['subscriptions']
                if config_name in subscriptions:
                    subscriptions.remove(config_name)
            
            logger.info(f"Client {client_id} unsubscribed from task updates for {config_name}")
            emit('unsubscribed', {'config_name': config_name})
        
        @self.socketio.on('get_all_tasks')
        def handle_get_all_tasks():
            """Send all current task statuses to requesting client."""
            emit('all_tasks', self.task_manager.profile)
    
    def _get_client_id(self) -> str:
        """Get a unique identifier for the current client."""
        from flask import request
        return f"{request.sid}"
    
    def broadcast_task_update(self, config_name: str, status_update: Dict[str, Any]):
        """
        Broadcast task status update to subscribed clients.
        
        Args:
            config_name: Name of the configuration
            status_update: Updated status information
        """
        self.socketio.emit('task_status_update', {
            'config_name': config_name,
            'update': status_update,
            'timestamp': datetime.datetime.now().isoformat()
        }, room=f"task_{config_name}")
        
        logger.debug(f"Broadcasted task update for {config_name}: {status_update}")
    
    def broadcast_task_start(self, config_name: str, task_type: str):
        """
        Broadcast task start event.
        
        Args:
            config_name: Name of the configuration
            task_type: Type of task being started
        """
        self.broadcast_task_update(config_name, {
            'event': 'task_started',
            'task_type': task_type,
            'status': 'busy'
        })
    
    def broadcast_task_complete(self, config_name: str, result: Dict[str, Any]):
        """
        Broadcast task completion event.
        
        Args:
            config_name: Name of the configuration
            result: Task result data
        """
        self.broadcast_task_update(config_name, {
            'event': 'task_completed',
            'result': result,
            'status': 'idle'
        })
    
    def broadcast_task_progress(self, config_name: str, progress_data: Dict[str, Any]):
        """
        Broadcast task progress update.
        
        Args:
            config_name: Name of the configuration
            progress_data: Progress information
        """
        self.broadcast_task_update(config_name, {
            'event': 'task_progress',
            'progress': progress_data
        })
    
    def get_connected_clients_count(self) -> int:
        """Get the number of connected clients."""
        return len(self.connected_clients)
    
    def get_client_subscriptions(self, client_id: str) -> list:
        """Get subscriptions for a specific client."""
        return self.connected_clients.get(client_id, {}).get('subscriptions', [])