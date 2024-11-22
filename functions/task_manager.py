from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.ssh_setup import SetupHost
from functions.run import RunTask
import datetime
import time
import os

class TaskManager:
  def __init__(self):
    # Get the current time with timezone information
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    self.timestamp_format = '%Y-%m-%d %H:%M:%S'
    self.init_time = now.strftime(self.timestamp_format)
    all_aws = ConfigLoader().load_all_aws_config()
    self.profile = {}
    for aws in all_aws:
      aws_detail ={}
      aws_detail['config_name'] = aws.get('configName')
      aws_detail['status'] = 'idle'
      aws_detail['aws_current_region'] = aws.get('region') or None
      aws_detail['last_task'] = {}
      # add aws_detail.get('configName') to the profile dictionary
      self.profile[aws.get('configName')] = aws_detail
  def print_profile(self):
    print(self.profile)
  def reload_profile(self, config_name):
    all_aws = ConfigLoader().load_all_aws_config()
    aws = next((aws for aws in all_aws if aws.get('configName') == config_name), None)
    last_task = self.profile[config_name]['last_task']
    aws_detail = {}
    aws_detail['config_name'] = aws.get('configName')
    aws_detail['current_task'] = None
    aws_detail['status'] = 'idle'
    aws_detail['aws_current_region'] = aws.get('region') or None
    aws_detail['last_task'] = last_task
    self.profile[config_name] = aws_detail
  def register_profile(self, config_name):
    if self.profile.get(config_name) == None:
      aws = ConfigLoader().load_aws_config(config_name)
      aws_detail = {}
      aws_detail['config_name'] = aws.get('configName')
      aws_detail['status'] = 'idle'
      aws_detail['aws_current_region'] = aws.get('region') or None
      aws_detail['last_task'] = {}
      self.profile[config_name] = aws_detail
  def set_start_task(self, **kwargs):
    config_name = kwargs.get('config_name')
    task_type = kwargs.get('task_type')
    self.profile[config_name]['status'] = 'busy'
    self.profile[config_name]['last_task']['start_time'] = datetime.datetime.now().strftime(self.timestamp_format)
    self.profile[config_name]['current_task'] = task_type
    self.profile[config_name]['last_task']['task_type'] = task_type
    task = RunTask()
    task_method = getattr(task, task_type)
    if not task_method:
      return 'Task not found'
    result = task_method(**kwargs)
    if result.get('status') == 'success':
      self.set_stop_task(config_name, 'success', result)
    else:
      self.set_stop_task(config_name, 'failed', result)
    self.reload_profile(config_name)
    return result
  def set_stop_task(self, config_name, result, data):
    self.profile[config_name]['status'] = 'idle'
    self.profile[config_name]['current_task'] = None
    self.profile[config_name]['last_task']['end_time'] = datetime.datetime.now().strftime(self.timestamp_format)
    self.profile[config_name]['last_task']['status'] = result
    self.profile[config_name]['last_task']['data'] = data
  def execute_task(self,**kwargs):
    task_type = kwargs.get('task_type')
    kwargs.pop('task_type')
    run_task_instance = RunTask()
    task_method = getattr(run_task_instance, task_type)
    if not task_method:
      return 'Task not found'
    result = task_method(**kwargs)
    return result
    