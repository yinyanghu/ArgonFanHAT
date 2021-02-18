#!/bin/bash

basedir="/tmp/ArgonFanHAT"

rm -rf "$basedir"
git clone https://github.com/yinyanghu/ArgonFanHAT.git "$basedir"

pip install smbus2 RPi.GPIO psutil

mkdir -p /etc/argonone
cp "$basedir/config.yaml" /etc/argonone/
cp "$basedir/argonone.service" /lib/systemd/system/
cp "$basedir/argonone.py" /usr/bin/

chmod 644 /lib/systemd/system/argonone.service

systemctl daemon-reload
systemctl enable argonone.service
systemctl start argonone.service

rm -rf "$basedir"
