[Unit]
Description=RemotePi HID Input Server Daemon
Documentation=https://github.com/TrueCoderSja/RemotePi

After=network.target pigpiod.service
Wants=pigpiod.service

[Service]
Type=simple
User=rsDev32
Group=rsDev32


WorkingDirectory=/home/rsDev32/HID


Environment=PYTHONUNBUFFERED=1


ExecStart=/usr/bin/python3 /home/rsDev32/HID/hid_server.py

Restart=on-failure
RestartSec=5s

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
