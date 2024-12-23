# Node-Test-Bench

code for node testing

# Test Bench Fixture

Test fixture for nodes has a controller, connector for load, and cables for connecting to node. It also has a single board computer for running a python test script.

# Single Board Computer

This linux computer (Raspberry Pi 4 Model B) runs the python test script. It has a small 480x320 display mounted to observe the test results.

A USB WiFi adapter can be used to network the computer to the node. But if you also want to use a USB keyboard/mouse, then connect an ethernet cable to network the computer and free a USB port.

## USB Ports - WiFi Configuration
1. Controller  
2. Load  
3. Barcode Scanner  
4. WiFi Adapter  

## USB Ports - Ethernet Configuration
1. Controller  
2. Load  
3. Barcode Scanner  
4. BT Keyboard/Mouse

# controller

Microcontroller (Arduino Nano) that manages the test fixture controls like relays, RS485, GPIO. It can detect the various 2out board versions (e.g. rev3, rev6, etc.).

It has a serial USB interface to a single board computer (SBC).

# load

Electronic load (Siglent SDL1020X-E 200W 150V 30A DC) is used to test both actuator outputs and the 24V rail. Relays switch between these outputs. Only one output connects to the load at a time.

# coap_client

This adds coap functionality to the test suite. This is generally faster and more reliable that interacting to the node through the serial console. The console has many bit errors, so it requires multiple attempts to get an accurate response. The coap interface is highly accurate on the first attempt.

# Serial Number Barcode Scanner

The test process is initiated by scanning a serial number barcode on each node housing.

# Test script

```
python3 test.py <test_id> <serial_number> <board_version> <optional arguments>

Optional Arguments:
  skip_db   # do not connect to database
  -v        # verbose console print mode, useful for troubleshooting console
  -s        # scan subnet for IP address matching serial number.
            # this requires at least test_id and serial_number arguments
            # e.g. python3 test.py 1 60010 -s
```

# Test config

`test.json`

```
{
    "subnet": "192.168.1.255",
    "code_version": "2out v Sep  5 2023 14:43:07",
    "cccv": 0,
    "maxw": 713,
    "load": {"CR":20,"dim":98,"power":60.0},
    "sensor1": true,
    "pdline": true
}
```

# Install
electronic load USB
```
sudo lsusb
Bus 001 Device 037: ID f4ec:1621 Atten Electronics / Siglent Technologies SDL1020X-E
```
sudo is required if you don't add the user to a group that can access the usb subsystem
```
sudo nano /etc/udev/rules.d/99-usb.rules
SUBSYSTEM=="usb", GROUP="plugdev", MODE="0660"
sudo usermod -a -G plugdev test
id test
uid=1000(test) gid=1000(test) groups=1000(test),4(adm),20(dialout),24(cdrom),27(sudo),29(audio),44(video),46(plugdev),60(games),100(users),104(input),106(render),108(netdev),999(spi),998(i2c),997(gpio),117(lpadmin)
```
Add github ssh key
```
sudo apt-get install git
git config --global user.email "boraw@mht-technologies.com"
git config --global user.name "Brad Oraw"
ssh-keygen -t ed25519 -C "boraw@mht-technologies.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```
python requirements
```
pip3 install -r requirements.txt
```
