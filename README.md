# Homematicip_heating_plug
This is a python-script, that triggers homematicip-events from a falmot12 floor-heating-block. 
It reads out the valve positions of all channels and triggers a plug on / off if minimum one valve is open.

It uses https://github.com/hahn-th/homematicip-rest-api, thanks a lot to all contributers!

Further documentation:
  - https://hahn-th.github.io/homematicip-rest-api/gettingstarted.html#getting-the-auth-token
  - https://deepwiki.com/hahn-th/homematicip-rest-api
    
# Installation

    sudo mkdir /opt/hmip
    sudo chown daniel /opt/hmip
    cd /opt/hmip/
    python3 -m venv /opt/hmip/
    . bin/activate
    pip3 install -U homematicip
    pip3 install asyncio, configparser, time, json
    
# Upgrade

    cd /opt/hmip/
    . bin/activate
    python -m pip install --upgrade pip
    pip install --upgrade virtualenv
    pip install --upgrade homematicip

# Tokengeneration


    cd /opt/hmip/
    . bin/activate
    bin/hmip_generate_auth_token

# systemd service creation

sudo nano /etc/systemd/system/hmip_elli_Heizungsschalter.service

    [Unit]
    Description=Homematic IP Auto Plug Control
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=simple
    User=daniel
    Group=daniel
    WorkingDirectory=/opt/hmip/bin/
    ExecStart=/opt/hmip/bin/python /opt/hmip/bin/hmip_elli_Heizungsschalter.py
    Restart=on-failure
    RestartSec=10
    Environment="PYTHONUNBUFFERED=1"
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=multi-user.target


# service activation

    sudo systemctl daemon-reload  
    sudo systemctl enable hmip_elli_Heizungsschalter.service  
    sudo systemctl start hmip_elli_Heizungsschalter.service  
