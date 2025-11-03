import serial
import time
import sys

# 串口配置
SERIAL_PORT = '/dev/ttyTHS1'
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1

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
        
        # 尝试读取串口返回
        response = ser.readline().decode().strip()
        if response:
            print(f"收到返回: {response}")
            
    except serial.SerialException as e:
        print(f"串口通信错误: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("串口已关闭")

def main():
    """测试主函数"""
    # 测试参数
    num_pulses = 100  # 脉冲数量
    frequency = 30.0  # 触发频率(Hz)
    
    print(f"开始测试串口通信...")
    print(f"串口: {SERIAL_PORT}")
    print(f"波特率: {SERIAL_BAUDRATE}")
    print(f"脉冲数量: {num_pulses}")
    print(f"触发频率: {frequency}Hz")
    
    # 发送测试命令
    send_pulse_command(num_pulses, frequency)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)