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
from flir_lib import FlirCamera
from thermal_lib import ThermalCamera

def create_save_directories(base_path):
    """创建保存目录结构"""
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    # 创建必要的子目录 - 只需要flir和thermal
    subdirs = ['flir', 'thermal']
    for subdir in subdirs:
        ensure_dir(os.path.join(save_path, subdir))
    
    print(f"数据将保存至: {save_path}")
    return save_path

def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)

class AsyncFlirThermalController:
    """FLIR和红外相机异步控制器"""
    
    def __init__(self, save_path):
        self.save_path = save_path
        self.executor = ThreadPoolExecutor(max_workers=6)  # 增加到6个线程
        
        # 同步事件
        self.capture_start_event = Event()
        self.capture_complete_event = Event()
        
        # 相机实例
        self.flir = None
        self.thermal_cam = None
        
        # 数据队列
        self.flir_queue = queue.Queue()
        
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
        
        # FLIR相机初始化
        futures.append(self.executor.submit(self._init_flir))
        
        # 红外相机初始化
        futures.append(self.executor.submit(self._init_thermal))
        
        # 等待所有初始化完成
        results = [future.result() for future in futures]
        return all(results)
    
    def _init_flir(self):
        """初始化FLIR相机"""
        try:
            self.flir = FlirCamera()
            if not self.flir.initialize():
                print("FLIR相机初始化失败")
                return False
            return True
        except Exception as e:
            print(f"FLIR相机初始化错误: {e}")
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

    def smart_thermal_preparation(self, thermal_cam, target_delay=3.0):
        """智能红外相机准备 - 借鉴测试脚本的成功策略"""
        print(f"🔧 红外相机智能准备中（{target_delay}秒）...")
        
        start_time = time.time()
        ready_signals = 0
        
        for i in range(int(target_delay), 0, -1):
            print(f"   ⏰ 红外相机准备倒计时: {i}秒...")
            
            # 检查相机状态
            check_start = time.time()
            while time.time() - check_start < 1.0:
                if hasattr(thermal_cam, 'captured_count'):
                    if thermal_cam.captured_count > 0:
                        ready_signals += 1
                time.sleep(0.1)
        
        # 额外等待确保完全稳定
        if ready_signals > 0:
            print(f"   ✅ 检测到红外相机活跃信号 ({ready_signals}个)")
        else:
            print(f"   ⚠️  未检测到活跃信号，额外等待0.5秒...")
            time.sleep(0.5)
        
        total_prep_time = time.time() - start_time
        print(f"   📊 红外相机准备完成: {total_prep_time:.2f}秒")
        
        return total_prep_time

    def start_capture(self):
        """开始异步采集"""
        print("开始FLIR和红外相机异步采集...")
        
        # 重置状态
        self.completed_cameras = 0
        self.capture_start_event.clear()
        self.capture_complete_event.clear()
        
        # 重置采集标志
        ACQUISITION_FLAG.value = 0
        RUNNING.value = 1
        
        # 清空队列
        while not self.flir_queue.empty():
            try:
                self.flir_queue.get_nowait()
            except queue.Empty:
                break
        
        # 启动数据处理线程
        self.executor.submit(self._flir_data_processor)
        self.executor.submit(self._thermal_data_processor)
        
        # 配置FLIR相机
        for i, cam in enumerate(self.flir.cam_list):
            try:
                cam.Init()
                nodemap = cam.GetNodeMap()
                
                if not self.flir.config_camera(nodemap):
                    print("FLIR相机配置失败")
                    return False
                
                cam.BeginAcquisition()
                
                # 启动采集线程
                self.executor.submit(self._thermal_capture_worker)
                
                
                # 关键修改：使用成功的智能等待策略
                print("📡 应用测试脚本的成功策略...")
                self.smart_thermal_preparation(self.thermal_cam, 4.0)
                self.executor.submit(self._flir_capture_worker, cam, nodemap)
                print(f"发送相机触发指令，采集 {NUM_IMAGES} 张图像...")
                
                # 发送触发指令
                self.send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
                
                # 等待采集完成
                self.capture_complete_event.wait(timeout=90)
                
                # 清理相机
                if cam.IsStreaming():
                    cam.EndAcquisition()
                cam.DeInit()
                del cam
                
                break  # 假设只有一个FLIR相机
                
            except Exception as ex:
                print(f'FLIR相机操作错误: {ex}')
                return False
        
        return True
    
    def _flir_capture_worker(self, cam, nodemap):
        """FLIR相机采集工作线程"""
        try:
            for i in range(NUM_IMAGES):
                if RUNNING.value == 0:
                    break
                    
                image_result = cam.GetNextImage(1000)
                if image_result.IsIncomplete():
                    print(f'FLIR图像不完整: {image_result.GetImageStatus()}')
                    image_result.Release()
                    continue
                
                # 快速获取数据并放入队列
                image_data = image_result.GetNDArray().copy()
                _, exposure_time = self.flir.read_chunk_data(image_result)
                
                self.flir_queue.put({
                    'index': i,
                    'data': image_data,
                    'exposure_time': exposure_time,
                    'timestamp': 0  # 不再收集真实时间戳，使用占位符
                })
                
                image_result.Release()
            
            print(f"FLIR相机采集完成，共采集 {NUM_IMAGES} 张图像")
            
            # 标记FLIR采集完成
            self._mark_camera_complete("FLIR")
            
        except Exception as e:
            print(f"FLIR采集线程错误: {e}")
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
    
    def _flir_data_processor(self):
        """FLIR数据处理线程"""
        images = {}
        exposure_times = {}
        timestamps = {}
        
        while True:
            try:
                # 从队列获取数据，超时10秒
                data = self.flir_queue.get(timeout=10)
                
                if data is None:  # 结束信号
                    break
                
                # 存储数据
                idx = data['index']
                images[idx] = data['data']
                exposure_times[idx] = data['exposure_time']
                timestamps[idx] = data['timestamp']
                
                self.flir_queue.task_done()
                
            except queue.Empty:
                # 检查是否应该退出
                if self.capture_complete_event.is_set():
                    break
                continue
        
        # 处理和保存数据
        if images:
            self._save_flir_data(images, exposure_times, timestamps)
    
    def _thermal_data_processor(self):
        """红外数据处理线程"""
        # 红外相机数据处理已经在thermal_lib中的process_frames方法中处理
        # 这里等待采集完成
        self.capture_complete_event.wait()
    
    def _save_flir_data(self, images, exposure_times, timestamps):
        """保存FLIR数据"""
        # 按索引排序
        sorted_indices = sorted(images.keys())
        
        # 跳过第一张图像（索引0）
        valid_indices = [i for i in sorted_indices if i > 0]
        
        # 准备数据数组
        image_array = np.array([images[i] for i in valid_indices])
        exposure_array = np.array([exposure_times[i] for i in valid_indices])
        
        # 保存数据（只传递图像和曝光时间）
        self.flir._save_data(image_array, exposure_array, self.save_path)
        print(f"已保存 {len(valid_indices)} 张FLIR图像")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止所有采集
            RUNNING.value = 0
            
            # 发送结束信号给处理线程
            try:
                self.flir_queue.put(None)
            except:
                pass
            
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
            if self.flir:
                try:
                    self.flir.cleanup()
                except Exception as e:
                    print(f"清理FLIR相机时出错: {e}")
            
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
    controller = AsyncFlirThermalController(save_path)
    
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