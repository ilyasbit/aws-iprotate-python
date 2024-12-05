import time

import colorlog

from functions.aws import Aws
from functions.connection import Socks5
from functions.main import ConfigLoader
from functions.service import ServiceManager
from functions.ssh_setup import SetupHost

logger = colorlog.getLogger()


class RunTask:
    def __init__(self):
        self.config = ConfigLoader()
        self.key_path = self.config.api_config["sshKeyPath"]
        self.username = "ubuntu"
        self.basesocks_port = 50000

    def change_region(self, **kwargs):
        try:
            config = ConfigLoader()
            config_name = kwargs.get("config_name")
            new_region = kwargs.get("new_region")
            if new_region is None:
                return {
                    "status": "failed",
                    "data": {"message": "New region is not provided"},
                }
            old_region = config.load_aws_config(config_name).get("region")
            if old_region == new_region:
                return {
                    "status": "failed",
                    "data": {"message": "New region is the same as the old region"},
                }
            aws = Aws(config_name)
            aws.login()
            aws.terminate_instance()
            self.config.change_region(config_name=config_name, new_region=new_region)
            aws = Aws(config_name)
            aws.login()
            logger.info(f"[{config_name}] Launching new instance in {new_region}")
            aws.launch_instance()
            aws_ip = aws.get_instance_address()
            order = aws.aws_config["order"]
            remote_path = "/etc/wireguard/wg0.conf"
            local_path = f"/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf"
            config.generate_profile_config(config_name, aws_ip)
            config.generate_peer_config(config_name)
            host = SetupHost(
                host=aws_ip,
                username="ubuntu",
                key_path=self.key_path,
                local_path=local_path,
                remote_path=remote_path,
            )
            host.login()
            host.setup()
            service = ServiceManager(f"iprotate_{order}_{config_name}")
            service.restart_iprotate_service()
            publicip = config.api_config["publicip"]
            proxy_port = self.basesocks_port + int(order)
            proxy_user = aws.aws_config["user"]
            proxy_pass = aws.aws_config["pass"]
            cconn = Socks5(
                proxy_host=publicip,
                proxy_port=proxy_port,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
            )
            for i in range(5):
                try:
                    newip = cconn.get_external_ip()
                    if newip == aws_ip:
                        logger.info(
                            f"[{config_name}] socks5 proxy is ready with external ip: {newip}"
                        )
                        break
                    else:
                        time.sleep(1)
                        continue
                except Exception as e:
                    logger.warning(e)
                    time.sleep(1)
                    continue
            return {
                "status": "success",
                "data": {
                    "old_region": old_region,
                    "new_region": new_region,
                    "new_ip": aws_ip,
                },
            }
        except Exception as e:
            logger.error(e)
            return {"status": "failed", "data": str(e)}

    def change_ip(self, **kwargs):
        try:
            config_name = kwargs.get("config_name")
            aws = Aws(config_name)
            aws.login()
            config = ConfigLoader()
            getnewip = aws.get_new_ip()
            aws_ip = getnewip.get("new_ip")
            order = aws.aws_config["order"]
            remote_path = "/etc/wireguard/wg0.conf"
            local_path = f"/opt/cloud-iprotate/profile_config/iprotate_{order}_{config_name}/wg0.conf"
            host = SetupHost(
                host=aws_ip,
                username=self.username,
                key_path=self.key_path,
                local_path=local_path,
                remote_path=remote_path,
            )
            config.generate_profile_config(config_name, aws_ip)
            config.generate_peer_config(config_name)
            host.login()
            host.setup()
            publicip = config.api_config["publicip"]
            service = ServiceManager(f"iprotate_{order}_{config_name}")
            try:
                service.stop()
            except Exception as e:
                logger.warning(e)

            service.restart_iprotate_service()
            proxy_port = self.basesocks_port + int(order)
            proxy_user = aws.aws_config["user"]
            proxy_pass = aws.aws_config["pass"]
            cconn = Socks5(
                proxy_host=publicip,
                proxy_port=proxy_port,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
            )
            for i in range(5):
                try:
                    newip = cconn.get_external_ip()
                    if newip == aws_ip:
                        logger.info(
                            f"[{config_name}] socks5 proxy is ready with external ip: {newip}"
                        )
                        break
                    else:
                        time.sleep(1)
                    continue
                except Exception as e:
                    logger.warning(e)
                    time.sleep(1)
                    continue
            return {"status": "success", "data": getnewip}
        except Exception as e:
            logger.error(e)
            return {"status": "failed", "data": str(e)}

    def change_whitelist(self, **kwargs):
        from functions.connection import Firewall

        try:
            config_name = kwargs.get("config_name")
            new_whitelist = kwargs.get("new_whitelist")
            config = ConfigLoader()
            config.set_value(config_name, "whitelist", new_whitelist)
            config.write_changes(config_name)
            fw = Firewall(config_name=config_name)
            fw.delete_rules()
            fw.apply_whitelist()
            return {
                "status": "success",
                "data": {"new_whitelist": new_whitelist},
            }
        except Exception as e:
            logger.error(e)
            return {"status": "failed", "data": str(e)}

    def reset(self, **kwargs):
        try:
            config_name = kwargs.get("config_name")
            aws = Aws(config_name)
            aws.login()
            aws.terminate_instance()
            config = ConfigLoader()
            config.set_value(config_name, "region", "us-east-2")
            config.set_value(config_name, "whitelist", "")
            config.set_value(config_name, "instanceid", "")
            config.set_value(config_name, "user", "")
            config.set_value(config_name, "pass", "")
            config.write_changes(config_name)
            return {"status": "success", "data": "config reset"}
        except Exception as e:
            logger.error(f"Error on reset {config_name} : {e}")
            return {"status": "failed", "data": str(e)}

    def change_auth(self, **kwargs):
        try:
            config_name = kwargs.get("config_name")
            aws = Aws(config_name)
            order = aws.aws_config["order"]
            new_user = kwargs.get("new_user")
            new_pass = kwargs.get("new_pass")
            config = ConfigLoader()
            config.set_value(config_name, "user", new_user)
            config.set_value(config_name, "pass", new_pass)
            config.write_changes(config_name)
            config.generate_3proxy_config(config_name)
            config.generate_shadowsocks_config(config_name)
            publicip = config.api_config["publicip"]
            service = ServiceManager(f"iprotate_{order}_{config_name}")
            service.stop()
            proxy_port = self.basesocks_port + int(order)
            cconn = Socks5(
                proxy_host=publicip,
                proxy_port=proxy_port,
                proxy_user=new_user,
                proxy_pass=new_pass,
            )
            service.start()
            for i in range(5):
                try:
                    newip = cconn.get_external_ip()
                    if newip:
                        logger.info(
                            f"[{config_name}] socks5 proxy is ready with external ip: {newip}"
                        )
                        break
                    else:
                        time.sleep(1)
                    continue
                except Exception as e:
                    logger.warning(e)
                    time.sleep(1)
                    continue
            return {
                "status": "success",
                "data": {"new_user": new_user, "new_pass": new_pass},
            }
        except Exception as e:
            logger.error(e)
            return {"status": "failed", "data": str(e)}
