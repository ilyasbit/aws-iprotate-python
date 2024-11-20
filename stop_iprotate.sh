#!/bin/bash

config_name=$1

echo "Stopping WireGuard interface $config_name"
wg-quick down /opt/cloud-iprotate/profile_config/${config_name}/${config_name}.conf

echo "Stopping 3proxy for $config_name"

pkill -f "3proxy /opt/cloud-iprotate/profile_config/${config_name}/proxy_${config_name}.cfg"
