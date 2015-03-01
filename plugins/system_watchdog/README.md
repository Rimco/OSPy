System Watchdog Readme  
====  

This plugin enable or disable Warchdog daemon in system. Broadcom BCM2708 chip on the RPi has a hardware watchdog. This can be very useful if your RPi is located remotely and locks up. However, this would not the preferred method of restarting the unit and in extreme cases this can result in file-system damage that could prevent the RPi from booting. If this occurs regularly you better find the root cause of the problem rather than fight the symptoms.
The watchdog daemon will send /dev/watchdog a heartbeat every 10 seconds. If /dev/watchdog does not receive this signal it will brute-force restart your Raspberry Pi.  
This plugin needs Watchdog. If not installed Watchdog, plugin installs Watchdog in to the system himself.  

Plugin automatic setup:
-----------

Enable Watchdog Kernel Module  
-----------

echo 'bcm2708_wdog' >> /etc/modules  
sudo modprobe bcm2708_wdog  

Install Watchdog Daemon  
-----------  

sudo apt-get install watchdog chkconfig    
chkconfig watchdog on    
sudo /etc/init.d/watchdog start  
sudo nano /etc/watchdog.conf  
Uncomment the line watchdog-device = /dev/watchdog  
You might also want to uncomment max-load-1, or add something like "max-load-1 = 24" to reset your Pi if the load average exceeds 24 in any 1-minute span.  
sudo /etc/init.d/watchdog restart  

Config file (/etc/watchdog.conf)  
-----------  

watchdog-device = /dev/watchdog  
max-load-1 = 24  
realtime = yes  
priority = 1  
log-dir = /home/pi/OSPy/plugins/system_watchdog/data/watchdoglog  

Watchdog daemon  
-----------  

For test type:  
: (){ :|:& };: