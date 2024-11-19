from systemd_service import Service
import dbus
import os
class ServiceManager:
  def __init__(self, service_name):
    self.service_name = service_name
    self.service = Service(f"iprotate@{service_name}")
  def restart_iprotate_service(self):
    service = Service(f"iprotate@{self.service_name}")
    service.restart()
  def stop(self):
    return self.service.stop()
  def start(self):
    return self.service.start()
  def reset_all(self):
    system_bus_address = os.getenv('DBUS_SYSTEM_BUS_ADDRESS')
    if system_bus_address:
        print(f"DBUS_SYSTEM_BUS_ADDRESS: {system_bus_address}")
    else:
        print("DBUS_SYSTEM_BUS_ADDRESS is not set. Using default path.")
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
        print(f"Resetting {service}")

if __name__ == '__main__':
  service = ServiceManager('iprotate_2_aws2')
  service.reset_all()