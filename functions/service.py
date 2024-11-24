from systemd_service import Service
import dbus
import os
import colorlog
logger = colorlog.getLogger()

class ServiceManager:
  def __init__(self, service_name):
    self.service_name = service_name
    self.service = Service(f"iprotate@{service_name}")
  def restart_iprotate_service(self):
    service = Service(f"iprotate@{self.service_name}")
    service.restart()
  def wg_reload(self):
    config_path = f'/opt/cloud-iprotate/profile_config/{self.service_name}/{self.service_name}.conf'
    response = os.system(f'wg syncconf {self.service_name} <(wg-quick strip {config_path})')
    exit_code = os.WEXITSTATUS(response)
    if exit_code == 0:
      return True
    return False
  def stop(self):
    return self.service.stop()
  def start(self):
    return self.service.start()
  def reset_all(self):
    os.environ['DBUS_SYSTEM_BUS_ADDRESS'] = 'unix:path=/var/run/dbus/system_bus_socket'
    bus = dbus.SystemBus()
    systemd = bus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
    manager = dbus.Interface(systemd, 'org.freedesktop.systemd1.Manager')
    # List all units
    units = manager.ListUnits()
    # Filter running services
    running_services = [unit[0] for unit in units if unit[4] == 'running']
    # Reset all running services with the name "iprotate@"
    for service in running_services:
      if service.startswith('iprotate@'):
        print(f"Stopping {service}")
        self.service_name = service.split('@')[1].split('.')[0]
        self.service = Service(f"iprotate@{self.service_name}")
        self.stop()


if __name__ == '__main__':
  service = ServiceManager('')
  service.reset_all()