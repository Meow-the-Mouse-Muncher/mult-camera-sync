import sys
import serial
import signal
from config import *
import time


def send_pulse_command(num_pulses, frequency):  
    """发送触发脉冲命令
    Args:
        num_pulses (int): 脉冲数量
        frequency (float): 触发频率
    """
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT)
        command = f"PULSE,{num_pulses},{frequency}\n"  
        ser.write(command.encode())  
        print(f"已发送触发命令: {command.strip()}")  
        time.sleep(0.1)  # 等待命令处理
    except serial.SerialException as e:
        print(f"串口通信错误: {e}")
    finally:
        if 'ser' in locals():
            ser.close()


if __name__ == "__main__":
    # 注册信号处理函数
    send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
    

    
