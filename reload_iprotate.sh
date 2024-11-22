#!/bin/bash

config_name=$1

echo "Reloading WireGuard interface $config_name"

running_wg=$(wg show $config_name 2>&1)
if [ $? == 0 ]; then
  wg syncconf $config_name <(wg-quick strip /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf)
else
  wg-quick up /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf
fi

3proxypid=$(pgrep -f "3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg")

if [ -z "$3proxypid" ]; then
  echo "3proxy for $config_name is not running"
  3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg &>/dev/null &
else
  pkill -USR1 -f "3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg"
  Pkill -SIGCONT -f "3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg"
fi
