import Jetson.GPIO as GPIO
import time

# 设置GPIO模式为BOARD（物理引脚编号）
GPIO.setmode(GPIO.BOARD)

# 定义要测试的GPIO引脚，比如Pin 12
output_pin = 11  # 可以根据你的实际需求修改这个引脚编号

# 将引脚设置为输出模式
GPIO.setup(output_pin, GPIO.OUT)
# GPIO.output(output_pin, GPIO.LOW)
# GPIO.cleanup()

try:
    while True:
        # 设置引脚为高电平
        GPIO.output(output_pin, GPIO.HIGH)
        print(f"引脚 {output_pin}: 高电平")
        time.sleep(0.02)

        # 设置引脚为低电平
        GPIO.output(output_pin, GPIO.LOW)
        print(f"引脚 {output_pin}: 低电平")
        time.sleep(0.02)

except KeyboardInterrupt:
    # 捕获Ctrl+C信号来终止程序
    print("程序终止")

finally:
    # 清理GPIO设置
    GPIO.cleanup()





    
# def trigger_star(out_io,fre,duty_cycle):
#     GPIO.setmode(GPIO.BOARD)
#     GPIO.setup(out_io, GPIO.OUT, initial=GPIO.LOW)
#     # pwm = GPIO.PWM(out_io, fre)	# 50Hz
#     # pwm.start(duty_cycle)	# 占空比为50%
#     # pwm.stop()
#     for i in range(NUM_IMAGES):
#         GPIO.output(out_io, GPIO.HIGH)
#         time.sleep(0.5/fre)
#         GPIO.output(out_io, GPIO.LOW)
#         time.sleep(0.5/fre)
#         print(i)

#     print("pulse is over ")
#     GPIO.cleanup()
#     return 0

