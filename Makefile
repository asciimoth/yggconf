clear:
	rm -rf yggconf
	rm -f yggconf.deb

build-deb: clear
	mkdir -p ./yggconf/DEBIAN
	mkdir -p ./yggconf/usr/share
	mkdir -p ./yggconf/lib/systemd/system
	cp control ./yggconf/DEBIAN/control
	cp yggconf.py ./yggconf/usr/share/yggconf.py
	cp yggconf.service ./yggconf/lib/systemd/system/yggconf.service
	dpkg-deb --build yggconf

intall-deb:
	apt install ./yggconf.deb
	systemctl daemon-reload
	systemctl enable yggconf
	systemctl start yggconf
