from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.ssh_setup import SetupHost
import datetime
import time
import os

class TaskManager:
  def __init__(self):
    # Get the current time with timezone information
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    timestamp_format = '%Y-%m-%d %H:%M:%S %Z'
    self.init_time = now.strftime(timestamp_format)
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
  def register_profile(self, config_name):
    if self.profile.get(config_name) == None:
      aws = ConfigLoader().load_aws_config(config_name)
      aws_detail = {}
      aws_detail['config_name'] = aws.get('configName')
      aws_detail['status'] = 'idle'
      aws_detail['aws_current_region'] = aws.get('region') or None
      aws_detail['last_task'] = {}
      self.profile[config_name] = aws_detail
  def set_start_task(self, config_name, task_type):
    self.profile[config_name]['status'] = 'busy'
    self.profile[config_name]['last_task']['start_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    self.profile[config_name]['current_task'] = task_type
    self.profile[config_name]['last_task']['task_type'] = task_type
  def set_stop_task(self, config_name, result, data):
    self.profile[config_name]['status'] = 'idle'
    self.profile[config_name]['current_task'] = None
    self.profile[config_name]['last_task']['end_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    self.profile[config_name]['last_task']['status'] = result
    self.profile[config_name]['last_task']['data'] = data
  def execute_task(self,**kwargs):
    task_type = kwargs.get('task_type')
    #remove task_type from kwargs
    kwargs.pop('task_type')
    #execute task_type function passing kwargs
    run.task_type(**kwargs)
    
  def run(self, config_name, task_type):
    if self.profile.get(config_name) == None:
      return 'Config name not found'
    if self.profile[config_name]['status'] == 'idle':
      self.set_start_task(config_name, task_type)
      return f'Process started for {config_name} with process type {task_type}'

class API:
  def __init__(self):
    self.config = ConfigLoader()
    self.config.load_api_config()
    self.running_process = {}
  def start_init(self):
    ServiceManager().reset_all()
    ConfigLoader().load_all_aws_config()
  def change_region(self, **kwargs):
    config_name = kwargs.get('config_name')
    new_region = kwargs.get('new_region')
    aws = Aws(config_name)
    aws.login()
    aws.terminate_instance()
    self.config.change_region(config_name=config_name, new_region=new_region)
    aws.launch_instance()
    aws_ip = aws.get_instance_address()
    order = aws.aws_config['order']
    remote_path = '/etc/wireguard/wg0.conf'
    local_path = f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf'
    host = SetupHost(host=aws_ip, username='ubuntu', key_path=self.config['api_config']['sshKeyPath'], local_path=local_path, remote_path=remote_path)
    host.login()
    host.setup()
    service = ServiceManager(f'iprotate_{order}_{config_name}')
    service.restart_iprotate_service()
  def new_ip(self, **kwargs):
    config_name = kwargs.get('config_name')
    aws = Aws(config_name)
    aws.login()
    aws_ip = aws.get_new_ip().get('new_ip')
    order = aws.aws_config['order']
    remote_path = '/etc/wireguard/wg0.conf'
    local_path = f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf'
    host = SetupHost(host=aws_ip, username='ubuntu', key_path=self.config['api_config']['sshKeyPath'], local_path=local_path, remote_path=remote_path)
    host.login()
    host.setup()
    service = ServiceManager(f'iprotate_{order}_{config_name}')
    service.stop()
    service.restart_iprotate_service()
