#!/bin/bash

file_path=/etc/wireguard/wg0.conf

nic=$(ip route get 8.8.8.8 | sed -nr 's/.*dev ([^\ ]+).*/\1/p')

#replace eth0 with the name of your network interface on file_path

sed -i "s/eth0/$nic/g" $file_path
