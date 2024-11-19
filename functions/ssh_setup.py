import paramiko
from functions.main import ConfigLoader

class SSHSetup:
    def __init__(self, **kwargs):
        self.host = kwargs.get('host')
        self.username = kwargs.get('username')
        self.key_path = kwargs.get('key_path')
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        self.ssh.connect(self.host, username=self.username, key_filename=self.key_path)
    
    def is_file_exists(self, remote_path):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo test -f {remote_path} && echo "File exists" || echo "File does not exist"')
        output = stdout.read().decode().strip()
        return output == "File exists"
    def package_is_installed(self, package_name):
        stdin, stdout, stderr = self.ssh.exec_command(f'sudo dpkg -l | grep {package_name}')
        output = stdout.read().decode().strip()
        return output != ''
    def install_package(self, package_name):
        is_installed = self.package_is_installed(package_name)
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
        installed = self.package_is_installed(package_name)
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

host = '13.229.218.255'
username = 'ubuntu'
key_path = '/root/.ssh/id_rsa'

ssh = SSHSetup(host=host, username=username, key_path=key_path)
ssh.connect()
print(ssh.remove_package('unattended-upgrades'))
print(ssh.install_package('wireguard'))
print(ssh.is_file_exists('/etc/wireguard/wg0.conf'))
wgonremote = ssh.read_file('/etc/wireguard/wg0.conf')
peer_config = ConfigLoader()
peer_config.load_api_config()
peer_config = peer_config.generate_peer_config('aws1')
#remove white space at the end of the line before comparing
peer_config = peer_config.rstrip()

#compare the output of the two print statements
if wgonremote == peer_config:
    print('Both configurations are the same')
else:
    ssh.copy_to_host(local_path='/opt/cloud-iprotate/profile_config/iprotate_1_aws1/wg0.conf', remote_path='/etc/wireguard/wg0.conf')
    print('Configuration copied to remote host')
    wgonremote = ssh.read_file('/etc/wireguard/wg0.conf')
    if wgonremote == peer_config:
        print('Both configurations are the same')
    else:
        print('Configuration not copied to remote host')

