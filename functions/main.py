import configparser
import json
import os

import colorlog
from filelock import FileLock

logger = colorlog.getLogger()


class ConfigLoader:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read("config.conf")
        self.api_config = self.load_api_config()
        self.all_aws_configs = self.load_all_aws_config()
        self.ssBasePort = 30000
        self.wgPortBase = 40000
        self.socks5PortBase = 50000
        self.httpPortBase = 60000

    def set_value(self, section, key, value):
        self.config.set(section, key, value)

    def write_changes(self, config_name):
        # Use a lock file to prevent race conditions
        lock = FileLock("config.conf.lock")
        with lock:
            # Read the existing configuration file
            temp_config = configparser.ConfigParser()
            temp_config.read("config.conf")

            # Update the target section with new values
            target_section = self.config[config_name]
            if config_name not in temp_config:
                temp_config[config_name] = {}
            for key in target_section:
                temp_config[config_name][key] = target_section[key]

            # Write the updated configuration back to the file
            with open("config.conf", "w") as file:
                temp_config.write(file)

    def change_region(self, **kwargs):
        config_name = kwargs.get("config_name")
        new_region = kwargs.get("new_region")
        aws_config = self.load_aws_config(config_name)
        aws_config["region"] = new_region
        self.set_value(config_name, "region", new_region)
        self.write_changes(config_name)

    def reload_config(self):
        self.config.read("config.conf")
        self.api_config = self.load_api_config()
        self.all_aws_configs = self.load_all_aws_config()

    def load_api_config(self):
        return {
            "apikey": self.config.get("api", "apikey"),
            "port": self.config.get("api", "port"),
            "interfaceWgPrivateKey": self.config.get("api", "interfacewgPrivateKey"),
            "interfaceWgPublicKey": self.config.get("api", "interfacewgPublicKey"),
            "peerWgPublicKey": self.config.get("api", "peerwgPublicKey"),
            "peerWgPrivateKey": self.config.get("api", "peerwgPrivateKey"),
            "publicip": self.config.get("api", "publicip"),
            "sshKeyPath": self.config.get("api", "sshKeyPath"),
        }

    def load_aws_config(self, config_name):
        if not self.config.has_option(config_name, "user"):
            self.config.set(config_name, "user", "")
        if not self.config.has_option(config_name, "pass"):
            self.config.set(config_name, "pass", "")
        if not self.config.has_option(config_name, "apikey"):
            self.config.set(config_name, "apikey", "")
        if not self.config.has_option(config_name, "whitelist"):
            self.config.set(config_name, "whitelist", "")
        if not self.config.has_option(config_name, "region"):
            self.config.set(config_name, "region", "us-east-1")
        if not self.config.has_option(config_name, "instanceid"):
            self.config.set(config_name, "instanceid", "")
        return {
            "configName": config_name,
            "order": self.config.get(config_name, "order"),
            "accessKey": self.config.get(config_name, "accessKey"),
            "secretKey": self.config.get(config_name, "secretKey"),
            "instanceId": self.config.get(config_name, "instanceId"),
            "region": self.config.get(config_name, "region"),
            "apikey": (self.config.get(config_name, "apikey") or ""),
            "whitelist": (self.config.get(config_name, "whitelist") or ""),
            "user": (self.config.get(config_name, "user") or ""),
            "pass": (self.config.get(config_name, "pass") or ""),
        }

    def reset_aws_config_order(self, config_name):
        self.config.set(config_name, "order", "")
        with open("config.conf", "w") as file:
            self.config.write(file)

    def reorder_aws_config(self, config_name, order: int):
        self.config.set(config_name, "order", str(order))
        with open("config.conf", "w") as file:
            self.config.write(file)

    def load_all_aws_config(self):
        aws_configs = []
        counter = 1
        for config_name in self.config.sections():
            if config_name == "api":
                continue
            self.reset_aws_config_order(config_name)
            self.reorder_aws_config(config_name, counter)
            counter += 1
            aws_configs.append(self.load_aws_config(config_name))
        return aws_configs

    def generate_peer_config(self, config_name):
        from functions.connection import Firewall

        try:
            fw = Firewall(config_name=config_name)
            logger.info("configuring firewall")
            fw.delete_rules()
            logger.info("deleting ufw rules")
            fw.apply_whitelist()
            logger.info("applying whitelist")
        except Exception as e:
            logger.error(e)
        aws_config = self.load_aws_config(config_name)
        peer_wg_port = "51821"
        interface_wg_public_key = self.api_config["interfaceWgPublicKey"]
        peer_wg_private_key = self.api_config["peerWgPrivateKey"]
        order = aws_config["order"]
        config_path = (
            f"/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}"
        )
        interface_ip = f"10.0.{order}.2/32"
        peer_ip = f"10.0.{order}.1/32"
        post_up_string = (
            "ufw route allow in on wg0 out on eth0; "
            + "ufw default allow incoming"
            + "; "
            + "sysctl -w net.ipv4.ip_forward=1"
            + "; "
            + "iptables -t nat -I POSTROUTING -o eth0 -j MASQUERADE"
        )
        pre_down_string = (
            "ufw route delete allow in on wg0 out on eth0; "
            + "iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
        )
        peer_config = configparser.ConfigParser()
        peer_config.add_section("Interface")
        peer_config.add_section("Peer")
        peer_config.set("Interface", "PrivateKey", peer_wg_private_key)
        peer_config.set("Interface", "ListenPort", peer_wg_port)
        peer_config.set("Interface", "Address", peer_ip)
        peer_config.set("Interface", "PostUp", post_up_string)
        peer_config.set("Interface", "PreDown", pre_down_string)
        peer_config.set("Interface", "MTU", "1500")
        peer_config.set("Peer", "PublicKey", interface_wg_public_key)
        peer_config.set("Peer", "AllowedIPs", interface_ip)
        # make sure directory exists
        os.makedirs(config_path, exist_ok=True)
        peer_config.write(open(f"{config_path}/wg0.conf", "w"))
        # read the file and return the content
        with open(f"{config_path}/wg0.conf", "r") as file:
            return file.read()
        logger.info(f"Generated peer config for {config_name}")

    def generate_shadowsocks_config(self, config_name):
        ss_config = {}
        user = self.config.get(config_name, "user")
        passwd = self.config.get(config_name, "pass")
        aws_config = self.load_aws_config(config_name)
        order = aws_config["order"]
        profile_name = f"iprotate_{order}_{config_name}"
        interface_wg_private_key = self.api_config["interfaceWgPrivateKey"]
        path = f"/opt/cloud-iprotate/profile_config/{profile_name}/shadowsocks.json"
        ss_config["server"] = "localhost"
        ss_config["server_port"] = self.ssBasePort + int(order)
        ss_config["password"] = interface_wg_private_key
        ss_config["method"] = "aes-128-gcm"
        ss_config["mode"] = "tcp_and_udp"
        ss_config["fast_open"] = True
        ss_config["locals"] = []
        ss_config["locals"] = []
        local_port = self.socks5PortBase + int(order)
        ss_config["locals"].append(
            {
                "local_address": "0.0.0.0",
                "local_port": int(local_port),
                "mode": "tcp_and_udp",
                "protocol": "socks",
            }
        )

        if user and passwd:
            auth_path = f"/opt/cloud-iprotate/profile_config/{profile_name}/auth.json"
            ss_config["locals"][0]["socks5_auth_config_path"] = auth_path
            auth_config = {
                "password": {"users": [{"user_name": user, "password": passwd}]}
            }
            auth_config_json = json.dumps(auth_config)
            with open(auth_path, "w") as file:
                file.write(auth_config_json)
        ss_config_json = json.dumps(ss_config)
        with open(path, "w") as file:
            file.write(ss_config_json)
        logger.info(f"Generated shadowsocks config for {config_name}")

    def generate_3proxy_config(self, config_name):
        aws_config = self.load_aws_config(config_name)
        order = aws_config["order"]
        profile_name = f"iprotate_{order}_{config_name}"
        user = aws_config["user"]
        passwd = aws_config["pass"]
        httpPort = self.httpPortBase + int(order)
        interface_ip = f"10.0.{order}.2/32"
        proxy_config_string = (
            "nserver 8.8.8.8"
            + "\n"
            + "nserver 8.8.4.4"
            + "\n"
            + "nscache 65536"
            + "\n"
            + "allow *"
            + "\n"
            'logformat "G%H:%M:%S.%. %'
            + 'd-%m-%y %z  %N.%p %E %U %C:%c %R:%r %O %I %h %T"'
            + "\n"
            "log "
            + '"/opt/cloud-iprotate/profile_config/'
            + profile_name
            + "/log.txt"
            + '"'
            + "\n"
        )
        if user and passwd:
            proxy_config_string += "auth strong" + "\n"

        proxy_config_string += (
            "proxy -n -p"
            + str(httpPort)
            + " -i0.0.0.0"
            + " -e"
            + interface_ip.split("/", 1)[0]
            + "\n"
        )

        if user and passwd:
            proxy_config_string += f"users {user}:CL:{passwd}" + "\n"

        os.makedirs(f"profile_config/{profile_name}", exist_ok=True)
        with open(
            f"profile_config/{profile_name}/proxy_{profile_name}.cfg", "w"
        ) as file:
            file.write(proxy_config_string)
        logger.info(f"Generated 3proxy config for {config_name}")

    def generate_profile_config(self, config_name, newip):
        peer_wg_port = "51821"
        aws_config = self.load_aws_config(config_name)
        interface_wg_private_key = self.api_config["interfaceWgPrivateKey"]
        peer_wg_public_key = self.api_config["peerWgPublicKey"]
        interface_name = f"ip_{aws_config['order']}_{config_name}"
        profile_name = f"iprotate_{aws_config['order']}_{config_name}"
        order = aws_config["order"]
        wg_port = self.wgPortBase + int(order)
        interface_ip = f"10.0.{order}.2/32"
        peer_ip = f"10.0.{order}.1/32"
        post_up_string = (
            "ip rule add from "
            + interface_ip.split("/", 1)[0]
            + " table "
            + order
            + "; "
            + "ip route add default via 10.0."
            + order
            + ".1 dev "
            + interface_name
            + " table "
            + order
            + "; "
            + "wg set "
            + interface_name
            + " peer "
            + peer_wg_public_key
            + " allowed-ips "
            + "0.0.0.0/0"
        )
        pre_down_string = (
            "wg set "
            + interface_name
            + " peer "
            + peer_wg_public_key
            + " allowed-ips "
            + peer_ip
        )
        post_down_string = "ip rule del table " + order
        wg_config = configparser.ConfigParser()
        wg_config.add_section("Interface")
        wg_config.add_section("Peer")
        wg_config.set("Interface", "PrivateKey", interface_wg_private_key)
        wg_config.set("Interface", "ListenPort", str(wg_port))
        wg_config.set("Interface", "Address", interface_ip)
        wg_config.set("Interface", "PostUp", post_up_string)
        wg_config.set("Interface", "PreDown", pre_down_string)
        wg_config.set("Interface", "PostDown", post_down_string)
        wg_config.set("Interface", "MTU", "1500")
        if newip:
            wg_config.set("Peer", "Endpoint", f"{newip}:{peer_wg_port}")
        wg_config.set("Peer", "PublicKey", peer_wg_public_key)
        wg_config.set("Peer", "AllowedIPs", peer_ip)
        wg_config.set("Peer", "PersistentKeepalive", "25")
        # make sure directory exists
        os.makedirs(f"profile_config/{profile_name}", exist_ok=True)
        wg_config.write(
            open(f"profile_config/{profile_name}/{interface_name}.conf", "w")
        )
        logger.info(f"Generated profile config for {config_name}")
        self.generate_3proxy_config(config_name)
        self.generate_shadowsocks_config(config_name)
