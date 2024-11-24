from functions.aws import Aws
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.ssh_setup import SetupHost
from functions.connection import Socks5
import time
import colorlog
logger = colorlog.getLogger()

class RunTask:
  def __init__(self):
    self.config = ConfigLoader()
    self.key_path = self.config.api_config['sshKeyPath']
    self.username = 'ubuntu'
  def change_region(self, **kwargs):
    config = ConfigLoader()
    config_name = kwargs.get('config_name')
    new_region = kwargs.get('new_region')
    old_region = config.load_aws_config(config_name).get('region')
    if old_region == new_region:
      return {'status': 'failed', 'data': {
        'message': 'New region is the same as the old region'
      }}
    aws = Aws(config_name)
    aws.login()
    aws.terminate_instance()
    self.config.change_region(config_name=config_name, new_region=new_region)
    aws = Aws(config_name)
    aws.login()
    logger.info(f'[{config_name}] Launching new instance in {new_region}')
    aws.launch_instance()
    aws_ip = aws.get_instance_address()
    order = aws.aws_config['order']
    remote_path = '/etc/wireguard/wg0.conf'
    local_path = f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf'
    config.generate_profile_config(config_name, aws_ip)
    config.generate_peer_config(config_name)
    host = SetupHost(host=aws_ip, username='ubuntu', key_path=self.key_path, local_path=local_path, remote_path=remote_path)
    host.login()
    host.setup()
    service = ServiceManager(f'iprotate_{order}_{config_name}')
    service.restart_iprotate_service()
    publicip = config.api_config['publicip']
    proxy_port = int(f'5000{order}')
    proxy_user = aws.aws_config['user']
    proxy_pass = aws.aws_config['pass']
    cconn = Socks5(proxy_host=publicip, proxy_port=proxy_port, proxy_user=proxy_user, proxy_pass=proxy_pass)
    for i in range(5):
      try:
        newip = cconn.get_external_ip()
        if newip == aws_ip:
          logger.info(f'[{config_name}] socks5 proxy is ready with external ip: {newip}')
          break
        else:
          time.sleep(1)
          continue
      except Exception as e:
        logger.warning(e)
        time.sleep(1)
        continue
    return {'status': 'success', 'data': {
      'old_region': old_region,
      'new_region': new_region,
      'new_ip': aws_ip
    }}
  def change_ip(self, **kwargs):
    config_name = kwargs.get('config_name')
    aws = Aws(config_name)
    aws.login()
    config = ConfigLoader()
    getnewip = aws.get_new_ip()
    aws_ip = getnewip.get('new_ip')
    order = aws.aws_config['order']
    remote_path = '/etc/wireguard/wg0.conf'
    local_path = f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf'
    host = SetupHost(host=aws_ip, username=self.username, key_path=self.key_path, local_path=local_path, remote_path=remote_path)
    config.generate_profile_config(config_name, aws_ip)
    config.generate_peer_config(config_name)
    host.login()
    host.setup()
    publicip = config.api_config['publicip']
    service = ServiceManager(f'iprotate_{order}_{config_name}')
    service.stop()
    service.restart_iprotate_service()
    proxy_port = int(f'5000{order}')
    proxy_user = aws.aws_config['user']
    proxy_pass = aws.aws_config['pass']
    cconn = Socks5(
      proxy_host=publicip, 
      proxy_port=proxy_port, 
      proxy_user=proxy_user, 
      proxy_pass=proxy_pass)
    for i in range(5):
      try:
        newip = cconn.get_external_ip()
        if newip == aws_ip:
          logger.info(f'[{config_name}] socks5 proxy is ready with external ip: {newip}')
          break
        else:
          time.sleep(1)
          continue
      except Exception as e:
        logger.warning(e)
        time.sleep(1)
        continue
    return {'status': 'success', 'data': getnewip}