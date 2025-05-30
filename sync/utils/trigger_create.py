import Jetson.GPIO as GPIO
import time
NUM_IMAGES = 100
FRAMERATE = int(15) # fps
EXPOSURE_TIME = 50000 # us
expose_time = EXPOSURE_TIME #us
frequency =int(FRAMERATE) # 设置频率
duty_cycle = 50 # 设置占空比为50
trigger_io = 11
GPIO.setmode(GPIO.BOARD)
# GPIO.setup(trigger_io, GPIO.OUT, initial=GPIO.LOW)
# trigger_flag = 0

def trigger_star(out_io,fre,duty_cycle):
    GPIO.setup(out_io, GPIO.OUT, initial=GPIO.LOW)
    # pwm = GPIO.PWM(out_io, fre)	# 50Hz
    # pwm.start(duty_cycle)	# 占空比为50%
    # pwm.stop()
    for i in range(NUM_IMAGES):
        GPIO.output(out_io, GPIO.HIGH)
        time.sleep(0.5/fre)
        GPIO.output(out_io, GPIO.LOW)
        time.sleep(0.5/fre)
    GPIO.cleanup()


trigger_star(trigger_io,frequency,duty_cycle)