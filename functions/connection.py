import socks
from urllib import request
from sockshandler import SocksiPyHandler

class Socks5:
    def __init__(self, **kwargs):
        self.proxy_host = kwargs.get('proxy_host')
        self.proxy_port = kwargs.get('proxy_port')
        self.proxy_user = kwargs.get('proxy_user') or None
        self.proxy_pass = kwargs.get('proxy_pass') or None
        self.timeout = 1

    def get_external_ip(self):
        opener = request.build_opener(SocksiPyHandler(socks.SOCKS5, 
        self.proxy_host,
        self.proxy_port,
        username=self.proxy_user,
        password=self.proxy_pass))
        request.install_opener(opener)
        try:
          return request.urlopen('http://ifconfig.me/ip', timeout=self.timeout).read().decode('utf-8')
        except Exception as e:
            raise Exception('Failed to get external IP') from e
