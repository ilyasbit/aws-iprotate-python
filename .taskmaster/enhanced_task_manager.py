"""
Enhanced Task Manager with WebSocket Integration

This module provides an enhanced TaskManager that broadcasts real-time updates
via WebSocket while maintaining compatibility with the existing API.
"""

import datetime
import threading
from typing import Optional, Dict, Any
import colorlog

from functions.main import ConfigLoader
from functions.run import RunTask

logger = colorlog.getLogger()


class EnhancedTaskManager:
    """
    Enhanced TaskManager with WebSocket broadcasting capabilities.
    
    This class extends the original TaskManager functionality while adding
    real-time WebSocket notifications for task status changes.
    """
    
    def __init__(self, websocket_manager=None):
        """
        Initialize Enhanced Task Manager.
        
        Args:
            websocket_manager: Optional WebSocketTaskManager instance for real-time updates
        """
        # Get the current time with timezone information
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.timestamp_format = "%Y-%m-%d %H:%M:%S"
        self.init_time = now.strftime(self.timestamp_format)
        self.websocket_manager = websocket_manager
        
        # Initialize profiles from existing configurations
        all_aws = ConfigLoader().load_all_aws_config()
        self.profile = {}
        for aws in all_aws:
            aws_detail = {}
            aws_detail["config_name"] = aws.get("configName")
            aws_detail["status"] = "idle"
            aws_detail["aws_current_region"] = aws.get("region") or None
            aws_detail["last_task"] = {}
            # add aws_detail.get('configName') to the profile dictionary
            self.profile[aws.get("configName")] = aws_detail

    def _notify_websocket(self, config_name: str, event_type: str, data: Dict[str, Any] = None):
        """
        Send notification to WebSocket manager if available.
        
        Args:
            config_name: Configuration name
            event_type: Type of event (start, complete, progress, etc.)
            data: Additional event data
        """
        if self.websocket_manager:
            try:
                if event_type == "task_started":
                    self.websocket_manager.broadcast_task_start(config_name, data.get("task_type"))
                elif event_type == "task_completed":
                    self.websocket_manager.broadcast_task_complete(config_name, data)
                elif event_type == "task_progress":
                    self.websocket_manager.broadcast_task_progress(config_name, data)
                elif event_type == "status_update":
                    self.websocket_manager.broadcast_task_update(config_name, data)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket notification: {e}")

    def reload_profile(self, config_name: str):
        """
        Reload profile configuration for a specific config.
        
        Args:
            config_name: Name of the configuration to reload
        """
        all_aws = ConfigLoader().load_all_aws_config()
        aws = next(
            (aws for aws in all_aws if aws.get("configName") == config_name), None
        )
        if aws:
            last_task = self.profile.get(config_name, {}).get("last_task", {})
            aws_detail = {}
            aws_detail["config_name"] = aws.get("configName")
            aws_detail["current_task"] = None
            aws_detail["status"] = "idle"
            aws_detail["aws_current_region"] = aws.get("region") or None
            aws_detail["last_task"] = last_task
            self.profile[config_name] = aws_detail
            
            # Notify WebSocket clients
            self._notify_websocket(config_name, "status_update", {
                "status": "idle",
                "profile_reloaded": True
            })

    def register_profile(self, config_name: str):
        """
        Register a new profile configuration.
        
        Args:
            config_name: Name of the configuration to register
        """
        if self.profile.get(config_name) is None:
            aws = ConfigLoader().load_aws_config(config_name)
            if aws:
                aws_detail = {}
                aws_detail["config_name"] = aws.get("configName")
                aws_detail["status"] = "idle"
                aws_detail["aws_current_region"] = aws.get("region") or None
                aws_detail["last_task"] = {}
                self.profile[config_name] = aws_detail
                
                # Notify WebSocket clients
                self._notify_websocket(config_name, "status_update", {
                    "status": "idle",
                    "profile_registered": True
                })

    def set_start_task(self, **kwargs):
        """
        Start a task with real-time WebSocket notifications.
        
        Args:
            **kwargs: Task parameters including config_name and task_type
            
        Returns:
            Task execution result
        """
        config_name = kwargs.get("config_name")
        task_type = kwargs.get("task_type")
        
        if not config_name or not task_type:
            return {"status": "failed", "data": "config_name and task_type are required"}
        
        # Ensure profile exists
        if config_name not in self.profile:
            self.register_profile(config_name)
        
        # Update status to busy
        self.profile[config_name]["status"] = "busy"
        self.profile[config_name]["task_start_time"] = datetime.datetime.now().strftime(
            self.timestamp_format
        )
        self.profile[config_name]["last_task"]["start_time"] = (
            datetime.datetime.now().strftime(self.timestamp_format)
        )
        self.profile[config_name]["current_task"] = task_type
        self.profile[config_name]["last_task"]["task_type"] = task_type
        
        # Notify WebSocket clients that task has started
        self._notify_websocket(config_name, "task_started", {"task_type": task_type})
        
        # Execute the task
        task = RunTask()
        task_method = getattr(task, task_type, None)
        if not task_method:
            result = {"status": "failed", "data": "Task not found"}
            self.set_stop_task(config_name, "failed", result)
            return result
        
        try:
            # Send progress notification
            self._notify_websocket(config_name, "task_progress", {
                "message": f"Executing {task_type}...",
                "stage": "execution"
            })
            
            result = task_method(**kwargs)
            
            if result.get("status") == "success":
                self.set_stop_task(config_name, "success", result)
            else:
                self.set_stop_task(config_name, "failed", result)
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            error_result = {"status": "failed", "data": str(e)}
            self.set_stop_task(config_name, "failed", error_result)
            result = error_result
        
        self.reload_profile(config_name)
        return result

    def set_stop_task(self, config_name: str, result: str, data: Dict[str, Any]):
        """
        Stop a task and update status with WebSocket notification.
        
        Args:
            config_name: Configuration name
            result: Task result status (success/failed)
            data: Task result data
        """
        self.profile[config_name]["status"] = "idle"
        self.profile[config_name]["current_task"] = None
        self.profile[config_name]["last_task"]["end_time"] = (
            datetime.datetime.now().strftime(self.timestamp_format)
        )
        self.profile[config_name]["last_task"]["status"] = result
        self.profile[config_name]["last_task"]["data"] = data
        
        # Notify WebSocket clients that task has completed
        self._notify_websocket(config_name, "task_completed", {
            "status": result,
            "data": data
        })

    def execute_task(self, **kwargs):
        """
        Execute a task without full lifecycle management.
        
        Args:
            **kwargs: Task parameters
            
        Returns:
            Task execution result
        """
        task_type = kwargs.get("task_type")
        if task_type:
            kwargs.pop("task_type")
        
        run_task_instance = RunTask()
        task_method = getattr(run_task_instance, task_type, None)
        if not task_method:
            return {"status": "failed", "data": "Task not found"}
        
        result = run_task_instance.task_method(**kwargs)
        return result

    def get_task_status(self, config_name: str) -> Dict[str, Any]:
        """
        Get current task status for a configuration.
        
        Args:
            config_name: Configuration name
            
        Returns:
            Current task status
        """
        if config_name not in self.profile:
            self.register_profile(config_name)
        
        return self.profile.get(config_name, {})

    def get_all_tasks(self) -> Dict[str, Any]:
        """
        Get all task statuses.
        
        Returns:
            Dictionary of all task profiles
        """
        return self.profile

    def start_task_async(self, **kwargs):
        """
        Start a task asynchronously using threading.
        
        Args:
            **kwargs: Task parameters
        """
        def task_runner():
            try:
                self.set_start_task(**kwargs)
            except Exception as e:
                logger.error(f"Async task execution failed: {e}")
                config_name = kwargs.get("config_name")
                if config_name:
                    self.set_stop_task(config_name, "failed", {"error": str(e)})
        
        thread = threading.Thread(target=task_runner, daemon=True)
        thread.start()
        return {"status": "started", "message": "Task started asynchronously"}