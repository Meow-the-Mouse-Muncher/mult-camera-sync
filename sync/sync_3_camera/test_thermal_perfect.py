import sys
import time
import datetime
import os
import serial
from threading import Thread, Event, Lock
import signal
import queue
from concurrent.futures import ThreadPoolExecutor
from config import *
from thermal_lib import ThermalCamera
from realtime_priority import print_system_info, setup_nice_thread

def create_save_directories(base_path):
    """创建保存目录结构"""
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    # 创建thermal子目录
    thermal_dir = os.path.join(save_path, 'thermal')
    if not os.path.exists(thermal_dir):
        os.makedirs(thermal_dir)
    
    print(f"数据将保存至: {save_path}")
    return save_path

class AsyncThermalController:
    """红外相机异步控制器"""
    
    def __init__(self, save_path):
        self.save_path = save_path
        self.executor = ThreadPoolExecutor(max_workers=6)  # 使用3个线程
        
        # 同步事件
        self.capture_complete_event = Event()
        
        # 相机实例
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
        """初始化红外相机"""
        future = self.executor.submit(self._init_thermal)
        return future.result()
    
    def _init_thermal(self):
        """初始化红外相机"""
        try:
            self.thermal_cam = ThermalCamera()
            # 不设置推流回调，专注于数据采集
            if not self.thermal_cam.connect(THERMAL_CAMERA_IP, THERMAL_CAMERA_PORT):
                print("红外相机初始化失败")
                return False
            
            if not self.thermal_cam.configure_camera(THERMAL_TEMP_SEGMENT, NUM_IMAGES, self.save_path):
                print("红外相机配置失败")
                return False
            
            print("红外相机初始化成功")
            return True
        except Exception as e:
            print(f"红外相机初始化错误: {e}")
            return False
    
    def start_capture(self):
        """开始异步采集"""
        print("开始红外相机采集...")
        
        # 重置状态
        self.completed_cameras = 0
        self.capture_complete_event.clear()
        
        # 重置采集标志
        RUNNING.value = 1
        
        # 启动数据处理线程（占位）
        self.executor.submit(self._thermal_data_processor)
        
        # 启动采集线程
        self.executor.submit(self._thermal_capture_worker)
        
        # 关键修复：发送触发信号
        # 使用红外相机的帧率而不是FLIR的帧率
        self.send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
        
        # 修复：正确计算超时时间
        expected_time = (NUM_IMAGES / FLIR_FRAMERATE) * 1.5 + 20 
        timeout = max(expected_time, 30)  # 至少60秒
        print(f"预期采集时间: {expected_time:.1f}秒, 设置超时: {timeout:.1f}秒")
        
        # 等待采集完成
        completed = self.capture_complete_event.wait(timeout=timeout)
        
        if not completed:
            print("采集超时！")
            RUNNING.value = 0
            return False
        
        return True
    
    def _thermal_capture_worker(self):
        """红外相机采集工作线程"""
        try:
            # 设置线程优先级和CPU绑定
            setup_nice_thread(
                nice_value=-20,        # 高优先级
                cpu_list=[0,1,2,3,4, 5]       # 绑定到ARM核心，避免和主程序冲突
            )
            
            # 启动红外相机采集
            if self.thermal_cam.start_capture():
                # 等待采集和处理完全完成
                self.thermal_cam.wait_for_completion()
                print("红外相机数据处理完成")
            
            # 标记红外相机完成（包括处理）
            self._mark_camera_complete()
            
        except Exception as e:
            print(f"红外相机采集线程错误: {e}")
            RUNNING.value = 0
            # 即使出错也标记完成，避免主线程无限等待
            self._mark_camera_complete()
    
    def _thermal_data_processor(self):
        """红外数据处理线程 - 占位线程"""
        # 等待采集完成
        self.capture_complete_event.wait()
        
        # 红外相机数据处理已经在thermal_lib中处理
        # 这里是占位线程，确保线程池资源分配
        if self.thermal_cam:
            time.sleep(1)  # 给红外相机额外时间完成处理
    
    def _mark_camera_complete(self):
        """标记相机完成采集"""
        with self.status_lock:
            self.completed_cameras += 1
            if self.completed_cameras >= 1:  # 只有一个红外相机
                print("红外相机采集完成！")
                self.capture_complete_event.set()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止所有采集
            RUNNING.value = 0
            
            # 设置采集完成事件
            if not self.capture_complete_event.is_set():
                self.capture_complete_event.set()
            
            # 清理红外相机资源
            if self.thermal_cam:
                try:
                    self.thermal_cam.cleanup()
                except Exception as e:
                    print(f"清理红外相机时出错: {e}")
            
            # 关闭线程池，等待所有任务完成
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=True)
                except Exception as e:
                    print(f"关闭线程池时出错: {e}")
                    
        except Exception as e:
            print(f"清理资源时出错: {e}")

def main():
    """主函数"""
    print("=== 红外相机多线程采集系统 ===")
    
    # 检查系统实时权限
    has_rt_perms = print_system_info()
    
    if not has_rt_perms:
        print("建议以root权限运行以获得最佳性能")
    
    # 初始化共享变量
    RUNNING.value = 1
    
    # 创建保存目录
    save_path = create_save_directories(BASE_DIR)
    
    # 创建异步控制器
    controller = AsyncThermalController(save_path)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, controller.signal_handler)
    
    try:
        # 初始化相机
        if not controller.initialize_cameras():
            print("相机初始化失败")
            return False
        
        # 开始异步采集
        if not controller.start_capture():
            print("采集失败")
            return False
        
        time.sleep(1)
        print("采集完成")
        return True
        
    except Exception as e:
        print(f"程序运行错误: {e}")
        return False
    finally:
        controller.cleanup()
        
        # 最终清理SDK
        try:
            from thermal_lib import ensure_sdk_cleanup
            ensure_sdk_cleanup()
        except Exception as e:
            print(f"清理SDK全局资源时出错: {e}")

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)