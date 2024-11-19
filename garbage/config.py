import re
import configparser

class ServiceConfig:
    def __init__(self, file_path):
        self.file_path = file_path
        self.config = configparser.ConfigParser()
        self.config.read(self.file_path)

    def get_value(self, section, key):
        return self.config.get(section, key)
    
    def set_value(self, section, key, value):
        self.config.set(section, key, value)

    def write_changes(self):
        with open(self.file_path, 'w') as file:
            self.config.write(file)
        

class ProxyConfig:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lines = self.read_config()

    def read_config(self):
        with open(self.file_path, 'r') as file:
            return file.readlines()

    def write_config(self):
        with open(self.file_path, 'w') as file:
            file.writelines(self.lines)

    def get_value(self, key):
        for line in self.lines:
            if line.startswith(key):
                return line.split(' ', 1)[1].strip()
        return None

    def set_value(self, key, value):
        for i, line in enumerate(self.lines):
            if line.startswith(key):
                self.lines[i] = f"{key} {value}\n"
                return
            # If the key is not found, add it to the end of the file
        self.lines.append(f"{key} {value}\n")

    def remove_value(self, key):
        self.lines = [line for line in self.lines if not line.startswith(key)]

    def add_user(self, username, password):
        users_line = self.get_value('users')
        if users_line:
            users_line += f" {username}:CL:{password}"
            self.set_value('users', users_line)
        else:
            self.set_value('users', f"{username}:CL:{password}")

    def remove_user(self, username):
        users_line = self.get_value('users')
        if users_line:
            users = users_line.split()
            users = [user for user in users if not user.startswith(username)]
            self.set_value('users', ' '.join(users))
    def remove_all_users(self):
        self.remove_value('users')

    def parse_parent_proxy(self):
        parent_line = self.get_value('parent')
        if parent_line:
            match = re.match(r'\d+ socks5\+ (\d+\.\d+\.\d+\.\d+) (\d+)', parent_line)
            if match:
                chain_address = match.group(1)
                chain_port = match.group(2)
                return chain_address, chain_port
        return None, None
    def set_parent_proxy(self, chain_address, chain_port):
        for i, line in enumerate(self.lines):
            if line.startswith('parent'):
                parts = line.split()
                parts[-2] = chain_address
                parts[-1] = chain_port
                self.lines[i] = ' '.join(parts) + '\n'
                return

if __name__ == '__main__':
    config = ProxyConfig('3proxy_template.cfg')
    # Accessing values
    dns_server = config.get_value('nserver')
    log_file = config.get_value('log')
    users = config.get_value('users')

    print(f"DNS Server: {dns_server}")
    print(f"Log File: {log_file}")
    print(f"Users: {users}")

    # Modifying values
    config.set_value('nserver', '8.8.4.4')

    # Adding a user
    config.add_user('user3', 'password3')

    # Removing a user
    config.remove_user('user1')

    chain_address, chain_port = config.parse_parent_proxy()
    print(f"Chain Address: {chain_address}")
    print(f"Chain Port: {chain_port}")
    config.set_parent_proxy('192.168.1.1', '8080')
    # Writing changes back to the file
    #config.remove_all_users()
    config.write_config()
    print(config.get_value('parent'))

    service_config = ServiceConfig('service_template.service')
    print(service_config.get_value('Service', 'ExecStart'))
    service_config.set_value('Service', 'ExecStart', '/usr/bin/python3 /path/to/app.py')
    service_config.write_changes()