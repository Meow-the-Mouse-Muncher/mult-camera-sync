import pigpio
import time
import os
ins="sudo pigpiod"
os.system(ins)
pi = pigpio.pi()

if not pi.connected:
   exit()

user_gpio = 13
expose_time = 10000 #us
frequency =int(10) # 设置频率为10Hz
duty_cycle = frequency/1000000.0
duty_cycle = int(expose_time*duty_cycle*1000000)
# duty_cycle = 100000 # 设置占空比为10%
# pi.hardware_PWM(user_gpio, frequency, duty_cycle)
# while(1):
#    i=0
# set pio low
pi.write(user_gpio, 0)
for i in range(11):
   # set pio high
   pi.write(user_gpio, 1)
   time.sleep(0.1)
   print(i)
   # set pio low
   pi.write(user_gpio, 0)

# while(1):
#    if input("Press Enter to trigger camera: ") == "":
#       break
print("stop camera")
# pi.hardware_PWM(user_gpio, 0, 0) # 停止PWM输出

pi.stop()