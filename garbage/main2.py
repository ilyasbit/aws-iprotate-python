import configparser
from urllib.parse import urlparse, urlunparse, urlencode
from pprint import pprint

class ConfigLoader:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.conf')
        self.api_config = self.load_api_config()
        self.aws_configs = []
        self.all_aws_configs = self.load_configurations()

    def load_api_config(self):
        return {
            'key': self.config.get('api', 'apiHostName'),
            'prefix': self.config.get('api', 'prefix'),
            'port': self.config.get('api', 'port'),
            'wgPrivateKey': self.config.get('api', 'wgPrivateKey'),
            'wgPublicKey': self.config.get('api', 'wgPublicKey'),
            'sshKeyPath': self.config.get('api', 'sshKeyPath'),
            'apiHostName': self.config.get('api', 'apiHostName')
        }

    def load_configurations(self):
        conf_list = self.config.sections()
        for config_name in conf_list:
            if config_name == 'api':
                continue
            self.load_configuration(config_name)
        return {
            'configs': {
                'api': self.api_config,
                'civo': self.civo_config_list,
                'tencent': self.tencent_config_list,
                'azure': self.azure_config_list,
                'aws': self.aws_config_list
            }
        }

    def load_configuration(self, config_name):
        config_type = self.config.get(config_name, 'type')
        socks5_port = self.config.get(config_name, 'socks5Port')
        http_port = self.config.get(config_name, 'httpPort')
        socks5_user = self.config.get(config_name, 'socks5User') if self.config.has_option(config_name, 'socks5User') else None
        socks5_pass = self.config.get(config_name, 'socks5Pass') if self.config.has_option(config_name, 'socks5Pass') else None
        
        change_ip_url = urlparse(f"http://{self.api_config['apiHostName']}:{self.api_config['port']}")
        path = f"{self.api_config['prefix']}/civo/newip" if config_type == 'civo' else f"{self.api_config['prefix']}/newip"
        change_ip_url = change_ip_url._replace(path=path)
        query = urlencode({'configName': config_name})
        change_ip_url = change_ip_url._replace(query=query)
        
        configuration = {
            'configName': config_name,
            'socks5Port': socks5_port,
            'httpPort': http_port,
            'changeIpUrl': urlunparse(change_ip_url)
        }

        if socks5_user and socks5_pass and config_type not in ['api']:
            configuration['socks5User'] = socks5_user
            configuration['socks5Pass'] = socks5_pass

        if config_type == 'tencent':
            configuration.update({
                'secretId': self.config.get(config_name, 'secretId'),
                'secretKey': self.config.get(config_name, 'secretKey'),
                'region': self.config.get(config_name, 'region'),
                'instanceId': self.config.get(config_name, 'instanceId')
            })
            self.tencent_config_list.append(configuration)
        elif config_type == 'azure':
            configuration.update({
                'clientId': self.config.get(config_name, 'clientId'),
                'clientSecret': self.config.get(config_name, 'clientSecret'),
                'tenantId': self.config.get(config_name, 'tenantId'),
                'subscriptionId': self.config.get(config_name, 'subscriptionId'),
                'resourceGroupName': self.config.get(config_name, 'resourceGroupName'),
                'publicIpName': self.config.get(config_name, 'publicIpName'),
                'ipConfigName': self.config.get(config_name, 'ipConfigName'),
                'nicName': self.config.get(config_name, 'nicName'),
                'vmName': self.config.get(config_name, 'vmName')
            })
            self.azure_config_list.append(configuration)
        elif config_type == 'aws':
            configuration.update({
                'accessKey': self.config.get(config_name, 'accessKey'),
                'secretKey': self.config.get(config_name, 'secretKey'),
                'instanceId': self.config.get(config_name, 'instanceId'),
                'region': self.config.get(config_name, 'region')
            })
            self.aws_config_list.append(configuration)
        elif config_type == 'civo':
            configuration.update({
                'token': self.config.get(config_name, 'token'),
                'cookie': self.config.get(config_name, 'cookie'),
                'region': self.config.get(config_name, 'region'),
                'instanceId': self.config.get(config_name, 'instanceId')
            })
            self.civo_config_list.append(configuration)

