import sys
import serial
import time
import os
from threading import Thread, Event, Lock
import signal
import queue
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from config import *
from event_lib import *
from thermal_lib import ThermalCamera

def create_save_directories(base_path):
    """创建保存目录结构"""
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    # 创建必要的子目录 - 只需要event和thermal
    subdirs = ['event', 'thermal']
    for subdir in subdirs:
        ensure_dir(os.path.join(save_path, subdir))
    
    print(f"数据将保存至: {save_path}")
    return save_path

def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)

class AsyncEventThermalController:
    """事件相机和红外相机异步控制器"""
    
    def __init__(self, save_path):
        self.save_path = save_path
        self.executor = ThreadPoolExecutor(max_workers=6)  # 增加到6个线程
        
        # 同步事件
        self.capture_start_event = Event()
        self.capture_complete_event = Event()
        
        # 相机实例
        self.prophesee_cam = None
        self.thermal_cam = None
        
        # 状态锁
        self.status_lock = Lock()
        self.completed_cameras = 0
        
    def signal_handler(self, sig, frame):
        """处理Ctrl+C信号"""
        print('\n正在清理资源并退出...')
        RUNNING.value = 0
        self.executor.shutdown(wait=False)
        sys.exit(0)
    
    def send_pulse_command(self, num_pulses, frequency):  
        """发送触发脉冲命令"""
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
    
    def initialize_cameras(self):
        """并行初始化相机"""
        futures = []
        
        # 事件相机初始化
        futures.append(self.executor.submit(self._init_prophesee))
        
        # 红外相机初始化
        futures.append(self.executor.submit(self._init_thermal))
        
        # 等待所有初始化完成
        results = [future.result() for future in futures]
        return all(results)
    
    def _init_prophesee(self):
        """初始化事件相机"""
        try:
            self.prophesee_cam = EventCamera(0, self.save_path)
            if not self.prophesee_cam.config_prophesee():
                print("Prophesee相机初始化失败")
                return False
            return True
        except Exception as e:
            print(f"事件相机初始化错误: {e}")
            return False
    
    def _init_thermal(self):
        """初始化红外相机"""
        try:
            self.thermal_cam = ThermalCamera()
            if not self.thermal_cam.connect(THERMAL_CAMERA_IP, THERMAL_CAMERA_PORT):
                print("红外相机连接失败")
                return False
            
            # 配置红外相机
            if not self.thermal_cam.configure_camera(THERMAL_TEMP_SEGMENT, NUM_IMAGES, self.save_path):
                print("红外相机配置失败")
                return False
            
            return True
        except Exception as e:
            print(f"红外相机初始化错误: {e}")
            return False

    def start_capture(self):
        """开始异步采集"""

        
        # 重置状态
        self.completed_cameras = 0
        self.capture_start_event.clear()
        self.capture_complete_event.clear()
        
        # 重置采集标志
        ACQUISITION_FLAG.value = 0
        RUNNING.value = 1
        
        # 启动数据处理线程
        self.executor.submit(self._event_data_processor)
        self.executor.submit(self._thermal_data_processor)
        

        self.executor.submit(self._prophesee_capture_worker)

        self.executor.submit(self._thermal_capture_worker)
        
        # 短暂延时确保所有线程就绪
        time.sleep(0.2)
        
        # 发送触发指令
        self.send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
        
        # 等待采集完成
        self.capture_complete_event.wait(timeout=90)
        
        return True
    
    def _prophesee_capture_worker(self):
        """事件相机采集工作线程"""
        try:
            # 启动事件流记录
            result = self.prophesee_cam.start_recording()
            
            # 标记事件相机采集完成
            self._mark_camera_complete("事件")
            
        except Exception as e:
            print(f"事件相机采集线程错误: {e}")
            RUNNING.value = 0
    
    def _thermal_capture_worker(self):
        """红外相机采集工作线程"""
        try:
            # 启动红外相机采集
            if self.thermal_cam.start_capture():
                # 等待采集和处理完全完成
                self.thermal_cam.wait_for_completion()
                print("红外相机采集完成")
            else:
                print("红外相机启动采集失败")
            
            # 设置采集标志，通知事件相机停止记录
            ACQUISITION_FLAG.value = 1
            
            # 标记红外相机完成
            self._mark_camera_complete("红外")
            
        except Exception as e:
            print(f"红外相机采集线程错误: {e}")
            RUNNING.value = 0

    def _mark_camera_complete(self, camera_name):
        """标记相机完成采集"""
        with self.status_lock:
            self.completed_cameras += 1
            if self.completed_cameras >= 2:  # 两个相机都完成
                print("所有相机采集完成！")
                self.capture_complete_event.set()
    
    def _event_data_processor(self):
        """事件数据处理线程"""
        # 等待采集完成后处理事件数据
        self.capture_complete_event.wait()
        
        try:
            triggers = self.prophesee_cam.prophesee_tirgger_found()
            if triggers is not None and len(triggers) > 0:
                print(f"成功检测到 {len(triggers)} 个触发信号")
            else:
                print("未检测到有效触发信号")
        except Exception as e:
            print(f"事件相机数据处理失败: {e}")
        
    
    def _thermal_data_processor(self):
        """红外数据处理线程"""

        self.capture_complete_event.wait()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止所有采集
            RUNNING.value = 0
            
            # 等待采集完成事件
            if not self.capture_complete_event.is_set():
                self.capture_complete_event.set()
            
            # 关闭线程池
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=True)
                except Exception as e:
                    print(f"关闭线程池时出错: {e}")
            
            # 清理相机资源
            if self.prophesee_cam:
                try:
                    # 事件相机清理
                    pass
                except Exception as e:
                    print(f"清理事件相机时出错: {e}")
            
            if self.thermal_cam:
                try:
                    self.thermal_cam.cleanup()
                except Exception as e:
                    print(f"清理红外相机时出错: {e}")
                
        except Exception as e:
            print(f"清理资源时出错: {e}")

def main():
    """主函数"""
    # 初始化共享变量
    RUNNING.value = 1
    ACQUISITION_FLAG.value = 0
    
    # 创建保存目录
    save_path = create_save_directories(BASE_DIR)
    
    # 创建异步控制器
    controller = AsyncEventThermalController(save_path)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, controller.signal_handler)
    
    try:
        # 并行初始化相机
        print("开始初始化相机...")
        if not controller.initialize_cameras():
            print("相机初始化失败")
            return False
        
        print("所有相机初始化成功")
        
        # 开始异步采集
        print("开始异步采集...")
        if not controller.start_capture():
            print("采集失败")
            return False
        
        # 短暂延时确保所有处理完成
        time.sleep(1)
        print("采集完成")
        return True
        
    except Exception as e:
        print(f"程序运行错误: {e}")
        return False
    finally:
        controller.cleanup()

    print("程序执行完成")
    return True

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)