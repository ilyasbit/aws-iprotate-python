#!/bin/bash

config_name=$1
wg_config="ip_$(echo $config_name | cut -d "_" -f2,3).conf"
interface_name=$(echo $wg_config | cut -d "." -f1)
echo "Starting WireGuard interface $config_name"
touch /opt/cloud-iprotate/profile_config/${config_name}/log.txt
if [ -f /opt/cloud-iprotate/profile_config/${config_name}/log.txt ]; then
  # check total line in config file
  total_line=$(wc -l </opt/cloud-iprotate/profile_config/${config_name}/log.txt)
  number_of_removed_line=$((total_line - 1000))

  if [[ $total_line -gt 1000 ]]; then
    tail -n 1000 /opt/cloud-iprotate/profile_config/${config_name}/log.txt >/opt/cloud-iprotate/profile_config/${config_name}/log.txt.tmp
    mv /opt/cloud-iprotate/profile_config/${config_name}/log.txt.tmp /opt/cloud-iprotate/profile_config/${config_name}/log.txt
  fi
fi

running_wg=$(wg show $interface_name 2>&1)
if [ $? == 0 ]; then
  wg syncconf $interface_name <(wg-quick strip /opt/cloud-iprotate/profile_config/${config_name}/${wg_config}) >>/opt/cloud-iprotate/profile_config/${config_name}/log.txt
else
  wg-quick up /opt/cloud-iprotate/profile_config/${config_name}/${wg_config} >>/opt/cloud-iprotate/profile_config/${config_name}/log.txt
fi

echo "Starting 3proxy for $config_name"

3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg &>/dev/null &
ssserver -c /opt/cloud-iprotate/profile_config/${config_name}/shadowsocks.json -v --outbound-bind-interface $interface_name >>/opt/cloud-iprotate/profile_config/${config_name}/log.txt 2>&1 &
sslocal -c /opt/cloud-iprotate/profile_config/${config_name}/shadowsocks.json >>/opt/cloud-iprotate/profile_config/${config_name}/log.txt 2>&1 &
tail -n1 -f /opt/cloud-iprotate/profile_config/${config_name}/log.txt
