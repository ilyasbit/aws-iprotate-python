import ipaddress
import os
import re
from configparser import ConfigParser
from urllib import request

import colorlog
import pyufw as ufw
import socks
from sockshandler import SocksiPyHandler

from functions.main import ConfigLoader

logger = colorlog.getLogger()


class Firewall:
    def __init__(self, **kwargs):
        self.config_name = kwargs.get("config_name")
        self.config = ConfigLoader()
        self.api_config = self.config.load_api_config()
        self.ssBasePort = 30000
        self.wgPortBase = 40000
        self.socks5PortBase = 50000
        self.httpPortBase = 60000
        self.aws_config = self.config.load_aws_config(self.config_name)
        self.order = int(self.aws_config.get("order"))
        self.app_name = f"iprotate_{self.order}"
        self.wgport = self.wgPortBase + self.order
        self.socks5port = self.socks5PortBase + self.order
        self.httpport = self.httpPortBase + self.order
        self.ssport = self.ssBasePort + self.order
        self.whitelist = self.aws_config.get("whitelist")
        if self.whitelist != "":
            self.whitelist = self.whitelist.split(",")
        app_config = ConfigParser()
        app_config.add_section(f"iprotate_{self.order}")
        app_config.set(
            f"iprotate_{self.order}",
            "title",
            f"iprotate_{self.order}",
        )
        app_config.set(
            f"iprotate_{self.order}",
            "description",
            f"ufw application config for iprotate_{self.order}",
        )
        app_config.set(
            f"iprotate_{self.order}",
            "ports",
            f"{self.socks5port},{self.httpport}/tcp|{self.socks5port}/udp",
        )
        # write app profile to file
        file_path = f"/etc/ufw/applications.d/iprotate_{self.order}"
        with open(file_path, "w") as configfile:
            app_config.write(configfile)
        try:
            os.system("ufw app list > /dev/null 2>&1")
            logger.info(f"app list updated {self.app_name}")
            os.system("ufw app update iprotate_{self.order} > /dev/null 2>&1")
            logger.info(f"add app profile {self.app_name}")
        except Exception as e:
            logger.error(e)

    def delete_rules(self):
        rule_list = ufw.status().get("rules")
        for index, rule in reversed(rule_list.items()):
            if re.search(rf" {self.app_name}$", rule):
                logger.info(f"removing rule {rule} on index {index}")
                ufw.delete(index)

    def apply_whitelist(self):
        if self.whitelist != "":
            for ip in self.whitelist:
                try:
                    ip = ip.strip()
                    if ipaddress.ip_network(ip, strict=False):
                        os.system("ufw allow from " + ip + " to any app " + 
                                self.app_name + 
                                " > /dev/null 2>&1")
                        logger.info(
                            f"add whitelist rule {ip} to profile {self.app_name}"
                        )
                except Exception:
                    continue
            try:
                logger.info(f"add reject rules to profie {self.app_name}")
                os.system("ufw reject from any to any app " + 
                        self.app_name +
                        " > /dev/null 2>&1")
            except Exception as e:
                logger.error(e)
        else:
            try:
                logger.info(f"add allow all rules to profile {self.app_name}")
                os.system(f"ufw allow from any to any app " + 
                        self.app_name + 
                        " > /dev/null 2>&1")
            except Exception as e:
                logger.error(e)


class Socks5:
    def __init__(self, **kwargs):
        self.proxy_host = kwargs.get("proxy_host")
        self.proxy_port = kwargs.get("proxy_port")
        self.proxy_user = kwargs.get("proxy_user") or None
        self.proxy_pass = kwargs.get("proxy_pass") or None
        self.timeout = 1

    def get_external_ip(self):
        opener = request.build_opener(
            SocksiPyHandler(
                socks.SOCKS5,
                self.proxy_host,
                self.proxy_port,
                username=self.proxy_user,
                password=self.proxy_pass,
            )
        )
        request.install_opener(opener)
        try:
            r = (
                request.urlopen("http://ifconfig.me/ip", timeout=self.timeout)
                .read()
                .decode("utf-8")
            )
            return r

        except Exception as e:
            raise Exception(f"Failed to get external IP, error: {e}")
