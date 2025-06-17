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
from flir_lib import FlirCamera

def create_save_directories(base_path):
    """创建保存目录结构"""
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    # 创建必要的子目录 - 只需要flir和event
    subdirs = ['event', 'flir']
    for subdir in subdirs:
        ensure_dir(os.path.join(save_path, subdir))
    
    print(f"数据将保存至: {save_path}")
    return save_path

def ensure_dir(path):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)

class AsyncFlirEventController:
    """FLIR和事件相机异步控制器"""
    
    def __init__(self, save_path):
        self.save_path = save_path
        self.executor = ThreadPoolExecutor(max_workers=6)  # 增加到6个线程
        
        # 同步事件
        self.capture_start_event = Event()
        self.capture_complete_event = Event()
        
        # 相机实例
        self.flir = None
        self.prophesee_cam = None
        
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
        
        # 事件相机初始化
        futures.append(self.executor.submit(self._init_prophesee))
        
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

    def start_capture(self):
        """开始异步采集"""
        print("开始FLIR和事件相机异步采集...")
        
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
        self.executor.submit(self._event_data_processor)
        
        # 配置FLIR相机
        for i, cam in enumerate(self.flir.cam_list):
            try:
                cam.Init()
                nodemap = cam.GetNodeMap()
                
                if not self.flir.config_camera(nodemap):
                    print("FLIR相机配置失败")
                    return False
                
                cam.BeginAcquisition()
                print("FLIR相机配置成功")
                
                # 启动所有采集线程
                self.executor.submit(self._flir_capture_worker, cam, nodemap)
                self.executor.submit(self._prophesee_capture_worker)
                
                # 短暂延时确保所有线程就绪
                time.sleep(0.2)
                
                # 发送触发指令
                print("发送触发指令...")
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
                    print("接收到停止信号，FLIR采集线程退出")
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
            
            # 设置采集标志，通知事件相机停止记录
            ACQUISITION_FLAG.value = 1
            
            # 标记FLIR采集完成
            self._mark_camera_complete("FLIR")
            
        except Exception as e:
            print(f"FLIR采集线程错误: {e}")
            RUNNING.value = 0
    
    def _prophesee_capture_worker(self):
        """事件相机采集工作线程"""
        try:
            # 启动事件流记录
            result = self.prophesee_cam.start_recording()
            print("事件相机采集完成")
            
            # 标记事件相机采集完成
            self._mark_camera_complete("事件")
            
        except Exception as e:
            print(f"事件相机采集线程错误: {e}")
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
        print("FLIR数据处理线程启动...")
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
                    print("采集完成，FLIR数据处理线程准备退出")
                    break
                continue
        
        # 处理和保存数据
        if images:
            print("FLIR数据处理完成，准备保存数据...")
            self._save_flir_data(images, exposure_times, timestamps)
    
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
        
        print("事件数据处理线程完成")
    
    def _save_flir_data(self, images, exposure_times, timestamps):
        """保存FLIR数据"""
        # 按索引排序
        sorted_indices = sorted(images.keys())
        
        # 跳过第一张图像（索引0）
        valid_indices = [i for i in sorted_indices if i > 0]
        
        if not valid_indices:
            print("没有有效的FLIR图像需要保存")
            return
        
        # 准备数据数组
        image_array = np.array([images[i] for i in valid_indices])
        exposure_array = np.array([exposure_times[i] for i in valid_indices])
        
        # 保存数据（只传递图像和曝光时间）
        self.flir._save_data(image_array, exposure_array, self.save_path)
        print(f"已保存 {len(valid_indices)} 张FLIR图像")
    
    def cleanup(self):
        """清理资源"""
        try:
            print("开始清理FLIR和事件相机控制器资源...")
            
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
                    print("FLIR相机资源已清理")
                except Exception as e:
                    print(f"清理FLIR相机时出错: {e}")
            
            if self.prophesee_cam:
                try:
                    # 事件相机清理
                    print("事件相机资源已清理")
                except Exception as e:
                    print(f"清理事件相机时出错: {e}")
                
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
    controller = AsyncFlirEventController(save_path)
    
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