"""
Standalone WebSocket test server

This file demonstrates the WebSocket functionality without requiring
all the AWS and task management dependencies.
"""

import datetime
from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'taskmaster_test_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Mock task manager for testing
class MockTaskManager:
    def __init__(self):
        self.profile = {
            'aws01': {
                'config_name': 'aws01',
                'status': 'idle',
                'aws_current_region': 'us-east-1',
                'last_task': {
                    'task_type': 'change_ip',
                    'status': 'success',
                    'start_time': '2025-01-01 12:00:00',
                    'end_time': '2025-01-01 12:01:00',
                    'data': {'new_ip': '192.168.1.100'}
                }
            },
            'aws02': {
                'config_name': 'aws02',
                'status': 'busy',
                'current_task': 'change_region',
                'aws_current_region': 'us-west-2',
                'last_task': {}
            }
        }

task_manager = MockTaskManager()
connected_clients = {}

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    client_id = f"client_{len(connected_clients) + 1}"
    connected_clients[client_id] = {
        'connected_at': datetime.datetime.now().isoformat(),
        'subscriptions': []
    }
    print(f"Client {client_id} connected")
    emit('connection_status', {'status': 'connected', 'client_id': client_id})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print("Client disconnected")

@socketio.on('subscribe_task')
def handle_subscribe_task(data):
    """Handle task subscription request."""
    config_name = data.get('config_name')
    
    if not config_name:
        emit('error', {'message': 'config_name is required'})
        return
    
    # Join room for this config
    join_room(f"task_{config_name}")
    
    # Send current task status
    current_status = task_manager.profile.get(config_name, {})
    emit('task_status', {
        'config_name': config_name,
        'status': current_status
    })
    
    print(f"Client subscribed to task updates for {config_name}")

@socketio.on('unsubscribe_task')
def handle_unsubscribe_task(data):
    """Handle task unsubscription request."""
    config_name = data.get('config_name')
    
    if not config_name:
        emit('error', {'message': 'config_name is required'})
        return
    
    # Leave room
    leave_room(f"task_{config_name}")
    
    print(f"Client unsubscribed from task updates for {config_name}")
    emit('unsubscribed', {'config_name': config_name})

@socketio.on('get_all_tasks')
def handle_get_all_tasks():
    """Send all current task statuses to requesting client."""
    emit('all_tasks', task_manager.profile)

@socketio.on('simulate_task_start')
def handle_simulate_task_start(data):
    """Simulate a task start for testing."""
    config_name = data.get('config_name', 'aws01')
    task_type = data.get('task_type', 'change_ip')
    
    # Update mock status
    if config_name in task_manager.profile:
        task_manager.profile[config_name]['status'] = 'busy'
        task_manager.profile[config_name]['current_task'] = task_type
    
    # Broadcast update
    socketio.emit('task_status_update', {
        'config_name': config_name,
        'update': {
            'event': 'task_started',
            'task_type': task_type,
            'status': 'busy'
        },
        'timestamp': datetime.datetime.now().isoformat()
    }, room=f"task_{config_name}")
    
    print(f"Simulated task start: {task_type} for {config_name}")

@socketio.on('simulate_task_complete')
def handle_simulate_task_complete(data):
    """Simulate a task completion for testing."""
    config_name = data.get('config_name', 'aws01')
    result = data.get('result', 'success')
    
    # Update mock status
    if config_name in task_manager.profile:
        task_manager.profile[config_name]['status'] = 'idle'
        task_manager.profile[config_name]['current_task'] = None
    
    # Broadcast update
    socketio.emit('task_status_update', {
        'config_name': config_name,
        'update': {
            'event': 'task_completed',
            'result': {'status': result, 'data': 'Simulated task result'},
            'status': 'idle'
        },
        'timestamp': datetime.datetime.now().isoformat()
    }, room=f"task_{config_name}")
    
    print(f"Simulated task complete: {result} for {config_name}")

@app.route('/')
def index():
    """Serve the WebSocket test client."""
    try:
        with open('.taskmaster/websocket_client.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
        <body>
            <h1>WebSocket Test Server</h1>
            <p>WebSocket server is running on this port.</p>
            <p>WebSocket client HTML file not found. Expected at: .taskmaster/websocket_client.html</p>
            <p>Use a WebSocket client to connect to this server for testing.</p>
        </body>
        </html>
        """

if __name__ == '__main__':
    print("Starting WebSocket Test Server...")
    print("Access at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)