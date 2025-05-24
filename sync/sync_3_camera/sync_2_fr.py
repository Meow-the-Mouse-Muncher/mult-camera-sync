import sys
import serial
import time
import os
from threading import Thread
import signal
from config import *
import time
from event_lib import *
from flir_lib import FlirCamera
from thermal_lib import ThermalCamera


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print('\n正在清理资源并退出...')
    RUNNING.value = 0
    sys.exit(0)

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

def create_save_directories(base_path):
    """创建保存目录结构
    Args:
        base_path (str): 基础保存路径
    Returns:
        str: 完整的保存路径
    """
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    # 创建必要的子目录
    subdirs = ['event', 'flir', 'thermal']
    for subdir in subdirs:
        ensure_dir(os.path.join(save_path, subdir))
    
    print(f"数据将保存至: {save_path}")
    return save_path

def main():
    """主函数"""
    # 初始化共享变量
    RUNNING.value = 1
    ACQUISITION_FLAG.value = 0
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建保存目录
    save_path = create_save_directories(BASE_DIR)

    flir = None
    prophesee_cam = None
    thermal_cam = None
    try:
        # 初始化FLIR相机
        flir = FlirCamera()
        if not flir.initialize():
            print("FLIR相机初始化失败")
            return False
        print("FLIR相机初始化成功")

        # 初始化红外相机
        thermal_cam = ThermalCamera()
        if not thermal_cam.connect(THERMAL_CAMERA_IP, THERMAL_CAMERA_PORT):
            print("红外相机初始化失败")
            return False
        print("红外相机初始化成功")
        # time.sleep(3)  # 等待相机稳定
        # 配置红外相机
        if not thermal_cam.configure_camera(THERMAL_TEMP_SEGMENT, NUM_IMAGES, save_path):
            print("红外相机配置失败")
            return False
        print("红外相机配置成功")

        # 相机采集流程
        for i, cam in enumerate(flir.cam_list):
            print(f'正在配置FLIR相机 {i}...')
            try:
                # 初始化相机
                cam.Init()
                nodemap = cam.GetNodeMap()

                # 配置相机
                if not flir.config_camera(nodemap):
                    print("FLIR相机配置失败")
                    return False
                print("FLIR相机配置成功")

                # 开始采集
                cam.BeginAcquisition()
                print("开始多线程采集...")
                
                flir_thread = Thread(target=flir.acquire_images, args=(cam, nodemap, save_path))
                thermal_thread = Thread(target=thermal_cam.start_capture)
                
                flir_thread.start()
                thermal_thread.start()
                
                # 发送触发指令
                send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
                flir_thread.join()
                
                # 等待红外相机采集和处理完成
                thermal_cam.wait_for_completion()


                # 确保相机停止采集
                if cam.IsStreaming():
                    cam.EndAcquisition()
                cam.DeInit()
                del cam

            except Exception as ex:
                print(f'相机操作错误: {ex}')
                return False

    except Exception as e:
        print(f"程序运行错误: {e}")
        return False
    finally:
        try:
            if flir:
                flir.cleanup()
                print("FLIR相机资源已清理")
            if thermal_cam:
                thermal_cam.cleanup()
                print("红外相机资源已清理")
        except Exception as e:
            print(f"清理相机资源时出错: {e}")

    print("程序执行完成")
    return True

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)

