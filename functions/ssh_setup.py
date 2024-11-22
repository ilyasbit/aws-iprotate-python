import paramiko
from functions.main import ConfigLoader
from functions.aws import Aws
from functions.service import ServiceManager
import time
import os, time

class SSHSetup:
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')
        self.username = kwargs.get('username')
        self.key_path = kwargs.get('key_path')
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, **kwargs):
        # try up to 10 times to connect to the remote host with timeout 1 second
        tries = kwargs.get('tries', 10)
        for i in range(tries):
            try:
                self.ssh.connect(self.host, username=self.username, key_filename=self.key_path, timeout=2.0)
                break
            except Exception as e:
                print(f'Failed to connect to {self.host} with error: {e}')
                time.sleep(1)
            if i == tries - 1:
                print("Failed to connect to " + self.host + " after " + str(tries) + " retries")
                return False
        if self.ssh.get_transport() is None:
            return False
        return True
    def is_file_exists(self, remote_path):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo test -f {remote_path} && echo "File exists" || echo "File does not exist"')
        output = stdout.read().decode().strip()
        return output == "File exists"
    def is_package_installed(self, package_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo dpkg -l | grep {package_name}')
        output = stdout.read().decode().strip()
        return output != ''
    def install_package(self, package_name):
        is_installed = self.is_package_installed(package_name)
        if is_installed:
            return True
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo apt update -y && sudo apt install {package_name} -y')
        output = stdout.read().decode().strip()
        exitcode = stdout.channel.recv_exit_status()
        if exitcode != 0:
            return False
        return True
    def remove_package(self, package_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo apt remove {package_name} -y && sudo apt autoremove -y && sudo apt purge {package_name} -y')
        installed = self.is_package_installed(package_name)
        output = stdout.read().decode().strip()
        if installed:
            return False
        return True
    def disable_service(self, service_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo systemctl stop {service_name} && sudo systemctl disable {service_name}')
        output = stdout.read().decode().strip()
        return output
    def enable_service(self, service_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo systemctl enable {service_name} && sudo systemctl start {service_name}')
        output = stdout.read().decode().strip()
        return output
    def stop_service(self, service_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo systemctl stop {service_name}')
        output = stdout.read().decode().strip()
        return output
    def ufw_allow_all(self):
        self.ssh.exec_command('sudo ufw default allow incoming').read().decode().strip()
        self.ssh.exec_command('sudo ufw default allow outgoing').read().decode().strip()
        #write the changes to the firewall

    def allow_ipv4_forwarding(self):
        stdin, stdout, stderr = self.ssh.exec_command(f'echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/99-sysctl.conf && sudo sysctl -p')
    def start_service(self, service_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo systemctl start {service_name}')
        output = stdout.read().decode().strip()
        return output
    def restart_service(self, service_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo systemctl restart {service_name}')
        output = stdout.read().decode().strip()
        return output
    def read_file(self, remote_path):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo cat {remote_path}')
        output = stdout.read().decode().strip()
        return output
    def copy_to_host(self, **kwargs):
        #copy file to remote host as root
        sftp = self.ssh.open_sftp()
        local_path = kwargs.get('local_path')
        remote_path = kwargs.get('remote_path')
        file_name = local_path.split('/')[-1]
        temp_path = f'/tmp/{file_name}'
        sftp.put(local_path, temp_path)
        sftp.close()
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo mv {temp_path} {remote_path}')
        output = stdout.read().decode().strip()
        is_file_exists = self.is_file_exists(remote_path)
        return is_file_exists
    def close(self):
        self.ssh.close()

class SetupHost:
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')
        self.username = kwargs.get('username')
        self.key_path = kwargs.get('key_path')
        self.local_path = kwargs.get('local_path')
        self.remote_path = kwargs.get('remote_path')
    def login(self):
        self.ssh = SSHSetup(host=self.host, username=self.username, key_path=self.key_path)
        self.ssh.connect()

    def setup(self):
        if not self.ssh:
            return False
        if self.ssh.is_package_installed('unattended-upgrades'):
            self.ssh.remove_package('unattended-upgrades')
        if not self.ssh.is_package_installed('wireguard'):
            self.ssh.install_package('wireguard')
        self.ssh.allow_ipv4_forwarding()
        self.ssh.copy_to_host(local_path=self.local_path, remote_path=self.remote_path)
        self.ssh.enable_service('wg-quick@wg0')
        self.ssh.close()

    def close(self):
        if not self.ssh:
            return False
        self.ssh = SSHSetup(host=self.host, username=self.username, key_path=self.key_path)
        self.ssh.close()


if __name__ == '__main__':
    username = 'ubuntu'
    key_path = '/root/.ssh/id_rsa'
    config_name = 'aws2'
    aws = Aws(config_name)
    aws.login()
    aws.terminate_instance()
    aws.launch_instance()
    aws_ip = aws.get_new_ip().get('new_ip')
    order = aws.aws_config['order']
    peer_ip = f'10.0.{order}.1'
    # setup wireguard on remote host
    remote_path = '/etc/wireguard/wg0.conf'
    local_path = f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf' 
    peer_config = ConfigLoader()
    peer_config.load_api_config()
    peer_config.generate_peer_config(config_name)
    peer_config.generate_profile_config(config_name, aws_ip)
    service = ServiceManager(f'iprotate_{order}_{config_name}')
    wg_reload = service.wg_reload()
    service.restart_iprotate_service()
    if wg_reload == False:
        service.restart_iprotate_service()
        peerconnect = SSHSetup(host=peer_ip, username=username, key_path=key_path)
        if peerconnect.connect() == False:
            host = SetupHost(host=aws_ip, username=username, key_path=key_path, local_path=local_path, remote_path=remote_path)
            host.login()
            host.setup()
    peerconnect = SSHSetup(host=peer_ip, username=username, key_path=key_path)
    if peerconnect.connect() == False:
        host = SetupHost(host=aws_ip, username=username, key_path=key_path, local_path=local_path, remote_path=remote_path)
        host.login()
        host.setup()
    