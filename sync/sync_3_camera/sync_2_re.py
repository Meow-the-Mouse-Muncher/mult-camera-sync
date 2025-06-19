import sys
import serial
import time
import datetime
import os
from threading import Thread, Event, Lock
import signal
import queue
import numpy as np
import cv2 as cv
from concurrent.futures import ThreadPoolExecutor
from config import *
from event_lib import *
from thermal_lib import ThermalCamera
from realtime_priority import print_system_info, setup_realtime_thread, SCHED_RR, setup_nice_thread

# 添加推流支持
os.environ['LD_LIBRARY_PATH'] = '/home/nvidia/code/mult-camera-sync/sync/sync_3_camera/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
from lib import streamPiper

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
        self.executor = ThreadPoolExecutor(max_workers=6)  # 使用6个线程
        
        # 同步事件
        self.capture_start_event = Event()
        self.capture_complete_event = Event()
        
        # 相机实例
        self.prophesee_cam = None
        self.thermal_cam = None
        
        # 数据队列
        self.thermal_queue = queue.Queue()
        self.event_queue = queue.Queue()
        
        # 状态锁
        self.status_lock = Lock()
        self.completed_cameras = 0
        
        # 推流相关属性
        self.stream_width = 600
        self.stream_height = 600
        self.streamPiper_instance = streamPiper.streamPiper(self.stream_width, self.stream_height)
        self.latest_thermal = None
        self.stream_lock = Lock()
        
        # 推流计数器相关属性（参考三相机逻辑）
        self.stream_push_interval = STREAM_PUSH_INTERVAL
    
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

    def _on_thermal_frame(self, thermal_img):
        """红外相机实时回调 - 参考三相机逻辑"""
        with self.stream_lock:
            
            self.latest_thermal = thermal_img
            
            # 推流红外图像（转换为RGB格式）
            if self.latest_thermal is not None:
                thermal_rgb = cv.cvtColor(self.latest_thermal, cv.COLOR_GRAY2RGB)
                self.streamPiper_instance.push(thermal_rgb)
    
    def initialize_cameras(self):
        """初始化所有相机"""
        # 使用线程池并行初始化
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
            print("Prophesee相机初始化成功")
            return True
        except Exception as e:
            print(f"事件相机初始化错误: {e}")
            return False
    
    def _init_thermal(self):
        """初始化红外相机"""
        try:
            self.thermal_cam = ThermalCamera()
            self.thermal_cam.set_realtime_callback(self._on_thermal_frame)
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
        print("开始异步多线程采集...")
        
        # 重置状态
        self.completed_cameras = 0
        self.capture_start_event.clear()
        self.capture_complete_event.clear()

        
        # 重置采集标志
        ACQUISITION_FLAG.value = 0
        RUNNING.value = 1  # 确保RUNNING标志被重置
        
        # 清空队列
        while not self.thermal_queue.empty():
            try:
                self.thermal_queue.get_nowait()
            except queue.Empty:
                break
        
        # 启动数据处理线程（保存Future引用）
        thermal_processor_future = self.executor.submit(self._thermal_data_processor)
        event_processor_future = self.executor.submit(self._event_data_processor)
        
        # 启动采集线程
        thermal_capture_future = self.executor.submit(self._thermal_capture_worker)
        # time.sleep(2.1)  # 确保红外相机先启动
        prophesee_capture_future = self.executor.submit(self._prophesee_capture_worker)
        
        # 发送触发指令
        self.send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
        
        # 等待采集完成
        completed = self.capture_complete_event.wait(timeout=50)  # 50秒超时
        
        if not completed:
            print("采集超时！")
            return False
        
        # 等待数据处理完成（参考三相机逻辑）
        print("等待数据处理完成...")
        try:
            thermal_processor_future.result(timeout=15)  # 15秒超时
            event_processor_future.result(timeout=10)   # 10秒超时
            print("所有数据处理完成")
        except Exception as e:
            print(f"数据处理出错: {e}")
        
        return True
    
    def _prophesee_capture_worker(self):
        """事件相机采集工作线程"""
        try:
            # 设置事件相机采集线程优先级和CPU绑定
            # setup_nice_thread(
            #     nice_value=-20,        # 高优先级
            #     cpu_list=[0, 1]       # 绑定到Denver核心
            # )
            
            # 启动事件流记录
            result = self.prophesee_cam.start_recording()
            print("事件相机采集完成")
            
            # 标记事件相机采集完成
            self._mark_camera_complete()
            
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
                print("红外相机数据处理完成")
            
            # 设置采集标志，通知事件相机停止记录
            ACQUISITION_FLAG.value = 1
            
            # 标记红外相机完成（包括处理）
            self._mark_camera_complete()
            
        except Exception as e:
            print(f"红外相机采集线程错误: {e}")
            RUNNING.value = 0
    
    def _mark_camera_complete(self):
        """标记相机完成采集"""
        with self.status_lock:
            self.completed_cameras += 1
            print(f"相机完成采集进度: {self.completed_cameras}/2")
            if self.completed_cameras >= 2:  # 两个相机都完成
                print("所有相机采集完成！")
                self.capture_complete_event.set()
    
    def _thermal_data_processor(self):
        """红外数据处理线程 - 参考三相机逻辑"""
        print("红外数据处理线程启动...")
        
        # 等待采集完成
        self.capture_complete_event.wait()
        
        # 红外相机数据处理已经在thermal_lib中的process_frames方法中处理
        # 这里添加额外的等待确保处理完全完成
        if self.thermal_cam:
            print("等待红外相机内部处理完成...")
            time.sleep(2)  # 给红外相机额外时间完成处理
        
        print("红外数据处理线程完成")
    
    def _event_data_processor(self):
        """事件数据处理线程 - 参考三相机逻辑"""
        print("事件数据处理线程启动...")
        
        # 等待采集完成后处理事件数据
        self.capture_complete_event.wait()
        
        # 给事件相机时间完成内部处理
        time.sleep(1)
        
        try:
            if self.prophesee_cam:
                triggers = self.prophesee_cam.prophesee_tirgger_found()
                if triggers is not None and len(triggers) > 0:
                    print(f"成功检测到 {len(triggers)} 个触发信号")
                else:
                    print("未检测到有效触发信号")
        except Exception as e:
            print(f"事件相机数据处理失败: {e}")
        
        print("事件数据处理线程完成")
    
    def cleanup(self):
        """清理资源 - 参考三相机逻辑"""
        try:
            print("开始清理异步控制器资源...")
            
            # 停止所有采集
            RUNNING.value = 0
            
            # 发送结束信号给处理线程
            try:
                self.thermal_queue.put(None)
            except:
                pass
            
            # 等待采集完成事件
            if not self.capture_complete_event.is_set():
                self.capture_complete_event.set()
            
            # 清理相机资源（在关闭线程池之前）
            if self.thermal_cam:
                try:
                    self.thermal_cam.cleanup()
                    print("红外相机资源已清理")
                except Exception as e:
                    print(f"清理红外相机时出错: {e}")
            
            if self.prophesee_cam:
                try:
                    print("事件相机资源已清理")
                except Exception as e:
                    print(f"清理事件相机时出错: {e}")
            
            # 最后关闭线程池，设置较短的等待时间
            if hasattr(self, 'executor') and self.executor:
                try:
                    print("正在关闭线程池...")
                    self.executor.shutdown(wait=False)  # 不等待，强制关闭
                    print("线程池已关闭")
                except Exception as e:
                    print(f"关闭线程池时出错: {e}")
                
        except Exception as e:
            print(f"清理资源时出错: {e}")

def main():
    """主函数 - Xavier NX优化版实时优先级支持"""
    print("=== 双相机同步采集系统 (事件+红外) (Xavier NX优化) ===")
    
    # 检查系统实时权限
    has_rt_perms = print_system_info()
    
    if not has_rt_perms:
        print("建议以root权限运行以获得最佳性能: sudo python3 sync_2_re.py")
        print("继续运行（性能可能受限）...")
    
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
        print("\n正在初始化相机...")
        if not controller.initialize_cameras():
            print("相机初始化失败")
            return False
        
        print("所有相机初始化成功")
        
        # 开始异步采集
        print("\n开始异步采集...")
        if not controller.start_capture():
            print("采集失败")
            return False
        
        # 短暂延时确保所有处理完成
        time.sleep(1)
        print("\n采集完成")
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

    print("程序执行完成")
    return True

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)