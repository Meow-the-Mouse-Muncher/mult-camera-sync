import serial
import time
from config import SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TIMEOUT # 假设配置在config.py中

def send_pulse_command(num_pulses, frequency):  
    """
    发送触发脉冲命令，并等待可选的响应。
    使用 'with' 语句确保串口被自动关闭。
    """
    try:
        # 'with' 语句会自动处理 ser.close()
        with serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT) as ser:
            # 等待串口稳定
            time.sleep(2) 
            
            command = f"PULSE,{num_pulses},{frequency}\n"  
            ser.write(command.encode('utf-8'))  
            print(f"已发送命令: {command.strip()}")
            
            # (可选) 等待并读取设备的返回信息
            response = ser.readline().decode('utf-8').strip()
            if response:
                print(f"收到响应: {response}")
            else:
                print("未收到响应 (超时)。")

    except serial.SerialException as e:
        print(f"串口错误: {e}")
        print(f"请检查端口 '{SERIAL_PORT}' 是否正确并且未被其他程序占用。")
    except Exception as e:
        print(f"发生未知错误: {e}")

# --- 使用示例 ---
if __name__ == '__main__':
    # 假设要发送100个脉冲，频率为50Hz
    PULSES = 3
    FREQ = 5
    send_pulse_command(PULSES, FREQ)