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
sudo /etc/init.d/watchdog restart  

Options (/etc/watchdog.conf)  
-----------  
* interval = 10  
Set the interval between two writes to the watchdog device. The kernel drivers expects a write command every minute. Otherwise the system will be rebooted. Default value is 10 seconds. An interval of more than a minute can only be used with the -f command-line option.  

* max-load-1 = 24  
Set the maximal allowed load average for a 1 minute span. Once this load average is reached the system is rebooted. Default value is 0. That means the load average check is disabled. Be careful not to this parameter too low. To set a value less then the predefined minimal value of 2, you have to use the -f commandline option.  

* watchdog-device = /dev/watchdog  
Set the watchdog device name. Default is to disable keep alive support. 

* realtime = yes  
If set to yes watchdog will lock itself into memory so it is never swapped out.  

* priority = 1  
Set the schedule priority for realtime mode.  

* test-timeout = 0  
User defined tests may only run for <timeout> seconds. Set to 0 for unlimited (second). 

Watchdog daemon  
-----------  

For test type:  
: (){ :|:& };: