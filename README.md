# yggconf
Simple python sript without dependences to autoconfig yggdrasil router  
## Usage
Yggconf script accepts the following parameters  
`python3 yggconf.py <src>, <dst>, <count>, <delay>, <cmd>, <ptls>`
where
+ src - source config file
+ dst - destination config file (/etc/yggdrasil.conf usualy)
+ count - number of peers to add
+ delay - delay in seconds between updating config
+ cmd - command to execute after the config is recreated (usualy "systemctl restart yggdrasil.service")
+ ptls - optional flag that enables preference for connections on port 443 over the tls protocol (false or true)

Sysd service installed by Makefile will use the following parameters  
`/usr/bin/python3 /usr/share/yggconf.py /etc/yggdrasil_raw.conf /etc/yggdrasil.conf 5 86400 "systemctl restart yggdrasil.service"`
## Instalation
### On deb based
#### With make
```sh
cp -f /etc/yggdrasil.conf /etc/yggdrasil_raw.conf
git clone https://github.com/DomesticMoth/yggconf.git
cd yggconf
make build-deb
sudo make intall-deb
```
#### Just downloading pre-builded package
```sh
wget https://github.com/asciimoth/yggconf/releases/download/0.1.0/yggconf.deb
sudo apt install ./yggconf.deb
sudo systemctl daemon-reload
sudo systemctl enable yggconf
sudo systemctl start yggconf
```
### On other systems
Just clone repo and run script  
It has no dependences except python interpreter
