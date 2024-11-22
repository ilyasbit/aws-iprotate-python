#!/bin/bash

config_name=$1

echo "Starting WireGuard interface $config_name"
if [ -f /opt/cloud-iprotate/profile_config/${config_name}/log.txt ]; then
  # check total line in config file
  total_line=$(wc -l </opt/cloud-iprotate/profile_config/${config_name}/log.txt)
  number_of_removed_line=$((total_line - 1000))

  if [[ $total_line -gt 1000 ]]; then
    tail -n 1000 /opt/cloud-iprotate/profile_config/${config_name}/log.txt >/opt/cloud-iprotate/profile_config/${config_name}/log.txt.tmp
    mv /opt/cloud-iprotate/profile_config/${config_name}/log.txt.tmp /opt/cloud-iprotate/profile_config/${config_name}/log.txt
  fi
fi

running_wg=$(wg show $config_name 2>&1)
if [ $? == 0 ]; then
  wg syncconf $config_name <(wg-quick strip /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf)
else
  wg-quick up /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf
fi

touch /opt/cloud-iprotate/profile_config/${config_name}/log.txt
echo "Starting 3proxy for $config_name"

3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg &>/dev/null &

tail -n1 -f /opt/cloud-iprotate/profile_config/${config_name}/log.txt
