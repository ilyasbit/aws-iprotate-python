#!/bin/bash

config_name=$1

echo "Stopping WireGuard interface $config_name"
running_wg=$(wg show $config_name 2>&1)
if [ $? == 0 ]; then
  wg-quick down /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf
else
  echo "WireGuard interface $config_name is not running"
fi

echo "Stopping 3proxy for $config_name"

pkill -f "3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg"
kill -9 $(ps aux | grep "ssserver -c /opt/cloud-iprotate/profile_config/${config_name}/shadowsocks.json --outbound-bind-interface $config_name" | awk '{print $2}')
kill -9 $(ps aux | grep "sslocal -c /opt/cloud-iprotate/profile_config/${config_name}/shadowsocks.json" | awk '{print $2}')
pkill -f "tail -n1 -f /opt/cloud-iprotate/profile_config/${config_name}/log.txt"
exit 0
