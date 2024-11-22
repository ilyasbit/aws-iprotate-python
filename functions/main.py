import configparser
from urllib.parse import urlparse, urlunparse, urlencode
import os

class ConfigLoader:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.conf')
        self.api_config = self.load_api_config()
        self.all_aws_configs = self.load_all_aws_config()
        self.wgPortBase = "4000"
        self.socks5PortBase = "5000"
        self.httpPortBase = "6000"

    def set_value(self, section, key, value):
        self.config.set(section, key, value)

    def write_changes(self):
        with open('config.conf', 'w') as file:
            self.config.write(file)    
    def change_region(self, **kwargs):
        config_name = kwargs.get('config_name')
        new_region = kwargs.get('new_region')
        aws_config = self.load_aws_config(config_name)
        aws_config['region'] = new_region
        self.set_value(config_name, 'region', new_region)
        self.write_changes()
    def reload_config(self):
        self.config.read('config.conf')
        self.api_config = self.load_api_config()
        self.all_aws_configs = self.load_all_aws_config()
    def load_api_config(self):
        return {
            'key': self.config.get('api', 'apiHostName'),
            'prefix': self.config.get('api', 'prefix'),
            'port': self.config.get('api', 'port'),
            'interfaceWgPrivateKey': self.config.get('api', 'interfacewgPrivateKey'),
            'interfaceWgPublicKey': self.config.get('api', 'interfacewgPublicKey'),
            'peerWgPublicKey': self.config.get('api', 'peerwgPublicKey'),
            'peerWgPrivateKey': self.config.get('api', 'peerwgPrivateKey'),
            'sshKeyPath': self.config.get('api', 'sshKeyPath'),
            'apiHostName': self.config.get('api', 'apiHostName')
        }
    def load_aws_config(self, config_name):
        if not self.config.has_option(config_name, 'user'):
            self.config.set(config_name, 'user', '')
        if not self.config.has_option(config_name, 'pass'):
            self.config.set(config_name, 'pass', '')
        return {
            'configName': config_name,
            'order': self.config.get(config_name, 'order'),
            'accessKey': self.config.get(config_name, 'accessKey'),
            'secretKey': self.config.get(config_name, 'secretKey'),
            'instanceId': self.config.get(config_name, 'instanceId'),
            'region': self.config.get(config_name, 'region'),
            'user': (self.config.get(config_name, 'user') or ""),
            'pass': (self.config.get(config_name, 'pass') or "")
        }
    def reset_aws_config_order(self, config_name):
        self.config.set(config_name, 'order', "")
        with open('config.conf', 'w') as file:
            self.config.write(file)
    def reorder_aws_config(self, config_name, order: int):
        self.config.set(config_name, 'order', str(order))
        with open('config.conf', 'w') as file:
            self.config.write(file)
    def load_all_aws_config(self):
        aws_configs = []
        counter = 1
        for config_name in self.config.sections():
            if config_name == 'api':
                continue
            self.reset_aws_config_order(config_name)
            self.reorder_aws_config(config_name, counter)
            counter += 1
            aws_configs.append(self.load_aws_config(config_name))
        return aws_configs
    def generate_peer_config(self, config_name):
        aws_config = self.load_aws_config(config_name)
        peer_wg_port = "51821"
        interface_wg_public_key = self.api_config['interfaceWgPublicKey']
        peer_wg_private_key = self.api_config['peerWgPrivateKey']
        order = aws_config['order']
        config_path=f'/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}'
        interface_ip = f'10.0.{order}.2/32'
        peer_ip = f'10.0.{order}.1/32'
        post_up_string = (
            "ufw route allow in on wg0 out on eth0; " + 
            "ufw default allow incoming" + "; " +
            "sysctl -w net.ipv4.ip_forward=1" + "; " +
            "iptables -t nat -I POSTROUTING -o eth0 -j MASQUERADE"
        )
        pre_down_string = (
            "ufw route delete allow in on wg0 out on eth0; " + 
            "iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
        )
        peer_config = configparser.ConfigParser()
        peer_config.add_section('Interface')
        peer_config.add_section('Peer')
        peer_config.set('Interface', 'PrivateKey', peer_wg_private_key)
        peer_config.set('Interface', 'ListenPort', peer_wg_port)
        peer_config.set('Interface', 'Address', peer_ip)
        peer_config.set('Interface', 'PostUp', post_up_string)
        peer_config.set('Interface', 'PreDown', pre_down_string)
        peer_config.set('Peer', 'PublicKey', interface_wg_public_key)
        peer_config.set('Peer', 'AllowedIPs', interface_ip)
        #make sure directory exists
        os.makedirs(config_path, exist_ok=True)
        peer_config.write(open(f'{config_path}/wg0.conf', 'w'))
        #read the file and return the content
        with open(f'{config_path}/wg0.conf', 'r') as file:
            return file.read()
    def generate_profile_config(self, config_name, newip):
        peer_wg_port = "51821"
        aws_config = self.load_aws_config(config_name)
        interface_wg_private_key = self.api_config['interfaceWgPrivateKey']
        peer_wg_public_key = self.api_config['peerWgPublicKey']
        interface_name = f'iprotate_{aws_config["order"]}_{config_name}'
        order = aws_config['order']
        wg_port = f'{self.wgPortBase}{order}'
        user = aws_config['user']
        passwd = aws_config['pass']
        socks5_port = f'{self.socks5PortBase}{order}'
        httpPort = f'{self.httpPortBase}{order}'
        interface_ip = f'10.0.{order}.2/32'
        peer_ip = f'10.0.{order}.1/32'
        post_up_string = (
            "ip rule add from " + interface_ip.split("/", 1)[0] + 
            " table " + order + "; " +
            "ip route add default via 10.0." + order + ".1 dev " + interface_name +" table " + order + "; " +
            "wg set " + interface_name +" peer " + peer_wg_public_key + " allowed-ips " + "0.0.0.0/0"

        )
        pre_down_string = (
            "wg set " + interface_name + " peer " + peer_wg_public_key + " allowed-ips " + peer_ip
        )
        post_down_string = (
            "ip rule del table " + order
        )
        wg_config = configparser.ConfigParser()
        wg_config.add_section('Interface')
        wg_config.add_section('Peer')
        wg_config.set('Interface', 'PrivateKey', interface_wg_private_key)
        wg_config.set('Interface', 'ListenPort', wg_port)
        wg_config.set('Interface', 'Address', interface_ip)
        wg_config.set('Interface', 'PostUp', post_up_string)
        wg_config.set('Interface', 'PreDown', pre_down_string)
        wg_config.set('Interface', 'PostDown', post_down_string)
        if newip:
            wg_config.set('Peer', 'Endpoint', f"{newip}:{peer_wg_port}")
        wg_config.set('Peer', 'PublicKey', peer_wg_public_key)
        wg_config.set('Peer', 'AllowedIPs', peer_ip)
        wg_config.set('Peer', 'PersistentKeepalive', '25')
        # make sure directory exists
        os.makedirs(f'profile_config/{interface_name}', exist_ok=True)
        wg_config.write(open(f'profile_config/{interface_name}/{interface_name}.conf', 'w'))
        proxy_config_string = (
            "nserver 8.8.8.8" + "\n" +
            "nserver 8.8.4.4" + "\n" + 
            "nscache 65536" + "\n" +
            "allow *" + "\n"
            "logformat \"G%H:%M:%S.%. %" + "d-%m-%y %z  %N.%p %E %U %C:%c %R:%r %O %I %h %T\"" + "\n"
            "log " + "\"/opt/cloud-iprotate/profile_config/" + interface_name + "/log.txt" + "\"" + "\n"
        )
        
        if user and passwd:
            proxy_config_string += "auth strong" + "\n"
        
        proxy_config_string += (
            "proxy -n -p" + httpPort + " -i0.0.0.0" + " -e" + interface_ip.split("/", 1)[0] + "\n" 
        )
        
        if user and passwd:
            proxy_config_string += f"users {user}:CL:{passwd}" + "\n"
        
        proxy_config_string += (
            "socks -n -u -p" + socks5_port + " -i0.0.0.0" + " -e" + interface_ip.split("/", 1)[0] + "\n"
        )
        if user and passwd:
            proxy_config_string += f"users {user}:CL:{passwd}" + "\n"

        os.makedirs(f'profile_config/{interface_name}', exist_ok=True)
        with open(f'profile_config/{interface_name}/proxy_{interface_name}.cfg', 'w') as file:
            file.write(proxy_config_string)

