import binascii
import hashlib

import ansible_runner
import boto3
import colorlog
import paramiko
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from .main import ConfigLoader

logger = colorlog.getLogger()


class Aws:
    def __init__(self, config_name):
        self.config = ConfigLoader()
        self.config_name = config_name
        self.aws_config = self.config.load_aws_config(config_name)
        self.user_data = """#cloud-config
            network:
            version: 2
            ethernets:
                eth0:
                match:
                    name: "en*"
                set-name: eth0
            """

    def format_fingerprint(self, fingerprint):
        # Convert the byte string to a hexadecimal string
        hex_fingerprint = binascii.hexlify(fingerprint).decode("utf-8")
        # Format the hexadecimal string to xx:xx:xx:xx format
        formatted_fingerprint = ":".join(
            hex_fingerprint[i : i + 2] for i in range(0, len(hex_fingerprint), 2)
        )
        return formatted_fingerprint

    def describe_images(self):
        try:
            self.ec2 = boto3.client(
                "ec2",
                region_name=self.aws_config["region"],
                aws_access_key_id=self.aws_config["accessKey"],
                aws_secret_access_key=self.aws_config["secretKey"],
            )
        except Exception as awsClientError:
            raise Exception(f"Error connecting to AWS: {awsClientError}")
        response = self.ec2.describe_images(
            Filters=[
                {
                    "Name": "name",
                    "Values": [
                        "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20240927",
                    ],
                },
            ]
        )
        return response

    def set_keypair(self):
        try:
            private_key = paramiko.RSAKey.from_private_key_file(
                self.config.api_config["sshKeyPath"]
            )
        except Exception as keyError:
            raise Exception(f"Error reading keypair file: {keyError}")
        public_key_string = private_key.get_base64()
        private_key_cryptography = serialization.load_pem_private_key(
            private_key.key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            password=None,
            backend=default_backend(),
        )
        public_key_pkcs8 = private_key_cryptography.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        fingerprint = hashlib.md5(public_key_pkcs8).digest()
        fingerprint = self.format_fingerprint(fingerprint)
        response = self.ec2.describe_key_pairs()
        for keypair in response["KeyPairs"]:
            if keypair["KeyFingerprint"] == fingerprint:
                self.key_pair_name = keypair["KeyName"]
                return keypair
        try:
            import datetime

            date = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            response = self.ec2.import_key_pair(
                KeyName=f"iprotate-{date}",
                PublicKeyMaterial=f"ssh-rsa {public_key_string}",
                TagSpecifications=[
                    {
                        "ResourceType": "key-pair",
                        "Tags": [{"Key": "role", "Value": "iprotate"}],
                    }
                ],
            )
        except Exception as keypairError:
            raise Exception(f"Error importing keypair: {keypairError}")
        self.key_pair_name = response["KeyName"]
        return response

    def create_security_group(self):
        response = self.ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "tag:role",
                    "Values": [
                        "iprotate",
                    ],
                },
            ]
        )

        def create_group_iprotate(self):
            return self.ec2.create_security_group(
                Description="iprotate",
                GroupName="iprotate",
                TagSpecifications=[
                    {
                        "ResourceType": "security-group",
                        "Tags": [{"Key": "role", "Value": "iprotate"}],
                    }
                ],
            )

        for security_group in response["SecurityGroups"]:
            if security_group["GroupName"] == "iprotate":
                self.security_group = security_group
            else:
                self.security_group = create_group_iprotate(self)
        if not hasattr(self, "security_group"):
            self.security_group = create_group_iprotate(self)
        response = self.ec2.describe_security_groups(
            GroupIds=[
                self.security_group["GroupId"],
            ]
        )
        for ip_permission in response["SecurityGroups"][0]["IpPermissions"]:
            if (
                ip_permission["IpProtocol"] == "-1"
                and ip_permission["IpRanges"][0]["CidrIp"] == "0.0.0.0/0"
                and ip_permission["IpRanges"][0]["Description"] == "Allow all traffic"
            ):
                return self.security_group
        self.ec2.authorize_security_group_ingress(
            GroupId=self.security_group["GroupId"],
            IpPermissions=[
                {
                    "IpProtocol": "-1",
                    "IpRanges": [
                        {"CidrIp": "0.0.0.0/0", "Description": "Allow all traffic"},
                    ],
                },
            ],
        )
        return self.security_group

    def launch_instance(self):
        instances_list = self.ec2.describe_instances()
        for instance in instances_list["Reservations"]:
            if hasattr(instance["Instances"][0], "Tags"):
                for tag in instance["Instances"][0]["Tags"]:
                    if (
                        tag["Key"] == "role"
                        and tag["Value"] == "iprotate"
                        and instance["Instances"][0]["State"]["Name"] != "terminated"
                        and instance["Instances"][0]["State"]["Name"] != "shutting-down"
                        and instance["Instances"][0]["State"]["Name"] != "terminating"
                    ):
                        instance_id = instance["Instances"][0]["InstanceId"]
                        self.config.set_value(
                            self.config_name, "instanceId", instance_id
                        )
                        self.config.write_changes(self.config_name)
                        self.aws_config = self.config.load_aws_config(self.config_name)
                        return instance["Instances"][0]
        self.create_security_group()
        instance_type = self.get_instance_type_free_tier().get("InstanceType")
        try:
            self.ec2 = boto3.client(
                "ec2",
                region_name=self.aws_config["region"],
                aws_access_key_id=self.aws_config["accessKey"],
                aws_secret_access_key=self.aws_config["secretKey"],
            )
        except Exception as awsClientError:
            raise Exception(f"Error connecting to AWS: {awsClientError}")
        self.set_keypair()
        instance = self.resource.create_instances(
            ImageId=self.describe_images().get("Images")[0].get("ImageId"),
            InstanceType=instance_type,
            KeyName=self.key_pair_name,
            UserData=self.user_data,
            SecurityGroups=[
                "iprotate",
            ],
            MaxCount=1,
            MinCount=1,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "role", "Value": "iprotate"}],
                }
            ],
        )
        new_instance_id = instance[0].id
        waiter = self.ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[new_instance_id])
        self.config.set_value(self.config_name, "instanceId", new_instance_id)
        self.config.write_changes(self.config_name)
        self.aws_config = self.config.load_aws_config(self.config_name)
        self.aws_config["instanceId"] = new_instance_id
        self.config.set_value(self.config_name, "instanceId", new_instance_id)
        self.config.write_changes(self.config_name)
        return self.ec2.describe_instances(InstanceIds=[new_instance_id])

    def terminate_instance(self):
        instances_list = self.ec2.describe_instances()
        if instances_list["Reservations"] is None:
            return
        for instance in instances_list["Reservations"]:
            instance_id = instance["Instances"][0]["InstanceId"]
            self.ec2.terminate_instances(InstanceIds=[instance_id])
        self.config.set_value(self.config_name, "instanceId", "")
        self.config.write_changes(self.config_name)
        instance_detail = {"InstanceId": "", "State": "terminated"}
        return instance_detail

    def get_instance_type_free_tier(self):
        instance_list = self.ec2.describe_instance_types(
            MaxResults=100, Filters=[{"Name": "free-tier-eligible", "Values": ["true"]}]
        )
        all_instance_types = instance_list.get("InstanceTypes", [])
        while "NextToken" in instance_list:
            next_token = instance_list["NextToken"]
            if not next_token:
                break
            instance_list = self.ec2.describe_instance_types(
                MaxResults=100,
                NextToken=next_token,
                Filters=[{"Name": "free-tier-eligible", "Values": ["true"]}],
            )
            all_instance_types.extend(instance_list.get("InstanceTypes", []))
        for instance in all_instance_types:
            if instance["VCpuInfo"]["DefaultCores"] == 1:
                return instance
        return None

    def run_ansible_playbook(self, playbook_path):
        for i in range(10):
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    self.get_instance_address(),
                    username="ubuntu",
                    key_filename=self.config.api_config["sshKeyPath"],
                    timeout=1,
                )
                break
            except Exception as sshError:
                if i == 9:
                    raise Exception(f"Error connecting to instance: {sshError}")
        ssh.close()
        envvars = {
            "interfaceWgPrivateKey": self.config.api_config["interfaceWgPrivateKey"],
            "interfaceWgPublicKey": self.config.api_config["interfaceWgPublicKey"],
            "peerWgPrivateKey": self.config.api_config["peerWgPrivateKey"],
            "peerWgPublicKey": self.config.api_config["peerWgPublicKey"],
            "order": self.aws_config["order"],
        }

        inventory = {
            "all": {
                "hosts": {
                    "aws": {
                        "ansible_host": self.get_instance_address(),
                        "ansible_user": "ubuntu",
                    }
                }
            }
        }
        try:
            ansible_runner.run(
                private_data_dir=".",
                playbook=playbook_path,
                inventory=inventory,
                envvars=envvars,
                tags="set-wg",
            )
        except Exception as ansibleError:
            raise Exception(f"Error running ansible playbook: {ansibleError}")

    def get_all_regions(self):
        ec2 = boto3.client(
            "ec2",
            region_name=self.aws_config["region"] or "us-east-1",
            aws_access_key_id=self.aws_config["accessKey"],
            aws_secret_access_key=self.aws_config["secretKey"],
        )
        response = ec2.describe_regions()
        return response["Regions"]

    def login(self):
        try:
            self.ec2 = boto3.client(
                "ec2",
                region_name=self.aws_config["region"],
                aws_access_key_id=self.aws_config["accessKey"],
                aws_secret_access_key=self.aws_config["secretKey"],
            )
        except Exception as awsClientError:
            raise Exception(f"Error connecting to AWS: {awsClientError}")
        response = (
            self.ec2.describe_regions(
                RegionNames=[
                    self.aws_config["region"],
                ]
            )
            .get("Regions", [])[0]
            .get("OptInStatus")
        )
        if response == "not-opted-in":
            raise Exception(f"Error connecting to AWS: {response}")
        self.resource = boto3.resource(
            "ec2",
            region_name=self.aws_config["region"],
            aws_access_key_id=self.aws_config["accessKey"],
            aws_secret_access_key=self.aws_config["secretKey"],
        )
        if self.resource is None:
            raise Exception("Error connecting to AWS")
        return True

    def get_instance_info(self):
        return self.ec2.describe_instances(InstanceIds=[self.aws_config["instanceId"]])

    def get_instance_address(self):
        response = self.ec2.describe_instances(
            InstanceIds=[self.aws_config["instanceId"]]
        )
        return response["Reservations"][0]["Instances"][0]["PublicIpAddress"]

    def associate_ip(self, ip_address):
        ec2 = boto3.client(
            "ec2",
            region_name=self.aws_config["region"],
            aws_access_key_id=self.aws_config["accessKey"],
            aws_secret_access_key=self.aws_config["secretKey"],
        )
        response = ec2.associate_address(
            InstanceId=self.aws_config["instanceId"], PublicIp=ip_address
        )
        return response

    def disassociate_and_release_ip(self):
        response = self.ec2.describe_addresses()
        for address in response["Addresses"]:
            if "Tags" in address:
                for tag in address["Tags"]:
                    if (
                        tag["Key"] == "instance"
                        and tag["Value"] == self.aws_config["instanceId"]
                    ):
                        try:
                            self.ec2.disassociate_address(
                                AssociationId=address["AssociationId"]
                            )
                        except Exception:
                            pass
                        try:
                            self.ec2.release_address(
                                AllocationId=address["AllocationId"]
                            )
                        except Exception:
                            pass
        return

    def allocate_and_associate_ip(self):
        response = self.ec2.allocate_address(
            TagSpecifications=[
                {
                    "ResourceType": "elastic-ip",
                    "Tags": [
                        {"Key": "instance", "Value": self.aws_config["instanceId"]}
                    ],
                }
            ]
        )
        self.ec2.associate_address(
            InstanceId=self.aws_config["instanceId"],
            AllocationId=response["AllocationId"],
        )
        self.disassociate_and_release_ip()
        return

    def get_new_ip(self):
        if self.aws_config["instanceId"] != "":
            logger.info(f'[{self.aws_config["configName"]}] Replacing IP address')
            old_ip = self.get_instance_address()
            self.disassociate_and_release_ip()
            self.allocate_and_associate_ip()
            new_ip = self.get_instance_address()
        else:
            logger.info(f'[{self.aws_config["configName"]}] Launching new instance')
            old_ip = None
            self.terminate_instance()
            self.launch_instance()
            new_ip = self.get_instance_address()
        logger.info(
            f'[{self.aws_config["configName"]}] old_ip: {old_ip}, new_ip: {new_ip}'
        )
        return {"old_ip": old_ip, "new_ip": new_ip}
