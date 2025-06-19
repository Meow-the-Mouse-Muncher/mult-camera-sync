import sys
import serial
import PySpin
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
from flir_lib import FlirCamera
from thermal_lib import ThermalCamera
from realtime_priority import print_system_info, setup_realtime_thread, SCHED_RR, setup_nice_thread

# 添加推流支持
os.environ['LD_LIBRARY_PATH'] = '/home/nvidia/code/mult-camera-sync/sync/sync_3_camera/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
from lib import streamPiper

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
        self.executor = ThreadPoolExecutor(max_workers=6)  # 使用6个线程
        
        # 同步事件
        self.capture_start_event = Event()
        self.capture_complete_event = Event()
        
        # 相机实例
        self.flir = None
        self.thermal_cam = None
        
        # 数据队列
        self.flir_queue = queue.Queue()
        self.thermal_queue = queue.Queue()
        
        # 状态锁
        self.status_lock = Lock()
        self.completed_cameras = 0
        
        # 推流相关属性
        self.stream_width = 600
        self.stream_height = 600
        self.streamPiper_instance = streamPiper.streamPiper(self.stream_width, self.stream_height)
        self.latest_flir = None
        self.latest_thermal = None
        self.stream_lock = Lock()
        
        # 推流计数器（参考三相机逻辑）
        self.stream_push_interval = STREAM_PUSH_INTERVAL
        
        # 分别为每个相机设置独立的计数器
        self._flir_frame_count = 0
        self._thermal_frame_count = 0
        
        # 记录最新的推流帧ID
        self.latest_flir_stream_id = -1
        self.latest_thermal_stream_id = -1
        
        # 推流状态标记
        self.flir_ready_for_stream = False
        self.thermal_ready_for_stream = False
        
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
        """红外相机实时回调 - 参考三相机同步推流逻辑"""
        with self.stream_lock:
            # thermal_img已经是推流帧处理后的结果
            self._thermal_frame_count += self.stream_push_interval  # 同步计数器
            
            self.latest_thermal = thermal_img
            self.latest_thermal_stream_id = self._thermal_frame_count // self.stream_push_interval
            self.thermal_ready_for_stream = True
 
            # 尝试同步推流
            self._try_sync_stream()

    def _try_sync_stream(self):
        """同步推流 - 只有两个相机都准备好才推流"""
        if (self.flir_ready_for_stream and self.thermal_ready_for_stream and
            self.latest_flir is not None and self.latest_thermal is not None and
            self.latest_flir_stream_id > 0 and self.latest_thermal_stream_id > 0):
            
            # 检查两个推流ID是否匹配或相近
            stream_id_diff = abs(self.latest_flir_stream_id - self.latest_thermal_stream_id)
            
            if stream_id_diff <= 1:  # 允许1个推流周期的差距
                # 执行推流
                half = self.stream_width // 2
                flir_rgb = cv.cvtColor(self.latest_flir, cv.COLOR_GRAY2RGB)
                thermal_rgb = cv.cvtColor(self.latest_thermal, cv.COLOR_GRAY2RGB)
                combined = np.zeros((self.stream_height, self.stream_width, 3), dtype=np.uint8)
                combined[:, :half] = flir_rgb[:, :half, :]
                combined[:, half:] = thermal_rgb[:, half:, :]
                self.streamPiper_instance.push(combined)

                self.flir_ready_for_stream = False
                self.thermal_ready_for_stream = False
            else:
                if self.latest_flir_stream_id < self.latest_thermal_stream_id:
                    # print("重置FLIR推流状态，等待下一个FLIR推流帧")
                    self.flir_ready_for_stream = False
                else:
                    # print("重置红外推流状态，等待下一个红外推流帧")
                    self.thermal_ready_for_stream = False
    
    def initialize_cameras(self):
        """初始化所有相机"""
        # 使用线程池并行初始化
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
            print("FLIR相机初始化成功")
            return True
        except Exception as e:
            print(f"FLIR相机初始化错误: {e}")
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
        """开始异步采集 - 修复版本"""
        print("开始异步多线程采集...")
        
        # 重置状态
        self.completed_cameras = 0
        self.capture_start_event.clear()
        self.capture_complete_event.clear()
        
        # 重置推流相关计数器和状态
        self._flir_frame_count = 0
        self._thermal_frame_count = 0
        self.latest_flir_stream_id = -1
        self.latest_thermal_stream_id = -1
        self.flir_ready_for_stream = False
        self.thermal_ready_for_stream = False
        
        # 重置采集标志
        ACQUISITION_FLAG.value = 0
        RUNNING.value = 1
        
        # 清空队列
        while not self.flir_queue.empty():
            try:
                self.flir_queue.get_nowait()
            except queue.Empty:
                break

        self.executor.submit(self._flir_data_processor)
        self.executor.submit(self._thermal_data_processor)  # 恢复红外数据处理线程

        # 配置FLIR相机
        for i, cam in enumerate(self.flir.cam_list):
            print(f'正在配置FLIR相机 {i}...')
            try:
                cam.Init()
                nodemap = cam.GetNodeMap()
                
                if not self.flir.config_camera(nodemap):
                    print("FLIR相机配置失败")
                    return False
                
                cam.BeginAcquisition()
                print("FLIR相机配置成功")
                
                # 启动采集线程 - 修复启动顺序
                self.executor.submit(self._thermal_capture_worker)
                self.executor.submit(self._flir_capture_worker, cam, nodemap)
                
                # 发送触发指令
                self.send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE)
                # 等待采集完成
                self.capture_complete_event.wait(timeout=50)
                # 清理相机
                try:
                    self.flir._disable_chunk_data(nodemap)
                    self.flir._reset_trigger(nodemap)

                except Exception as e:
                    print(f"重置FLIR相机设置时出错: {e}")
                    
                if cam.IsStreaming():
                    cam.EndAcquisition()

                
                cam.DeInit()
                del cam

                
                break  # 假设只有一个FLIR相机
            
            except Exception as ex:
                print(f'FLIR相机操作错误: {ex}')
                RUNNING.value = 0
                return False

    def _flir_capture_worker(self, cam, nodemap):
        """FLIR相机采集工作线程 - 参考三相机同步推流逻辑"""
        setup_nice_thread(
            nice_value=-15,        # 高优先级
            cpu_list=[0, 1]       # 绑定到Denver核心
        )
        try:
            for i in range(NUM_IMAGES):
                if RUNNING.value == 0:
                    break
                    
                image_result = cam.GetNextImage(1000)
                if image_result.IsIncomplete():
                    print(f'FLIR图像不完整: {image_result.GetImageStatus()}')
                    image_result.Release()
                    continue
                
                capture_time = datetime.datetime.now().timestamp()
                
                # 快速获取数据并放入队列
                image_data = image_result.GetNDArray().copy()
                _, exposure_time = self.flir.read_chunk_data(image_result)
                
                self.flir_queue.put({
                    'index': i,
                    'data': image_data,
                    'exposure_time': exposure_time,
                    'timestamp': capture_time
                })
                
                # 修改：使用独立的FLIR计数器，只在推流帧上处理
                with self.stream_lock:
                    self._flir_frame_count += 1
                    
                    # 检查是否到达推流帧
                    if self._flir_frame_count % self.stream_push_interval == 0:
                        # print(f"FLIR推流帧处理: 第{self._flir_frame_count}帧")
                        
                        # 只在推流帧上做resize
                        flir_img = cv.resize(image_data, (self.stream_width, self.stream_height))
                        self.latest_flir = flir_img
                        self.latest_flir_stream_id = self._flir_frame_count // self.stream_push_interval
                        self.flir_ready_for_stream = True
                        
                        # print(f"FLIR推流帧准备: 推流ID {self.latest_flir_stream_id}")
                        
                        # 尝试同步推流
                        self._try_sync_stream()
                    # 其他帧完全跳过图像处理
                
                image_result.Release()
            
            print(f"FLIR相机采集完成，共采集 {NUM_IMAGES} 张图像")
            
            # 标记FLIR采集完成
            self._mark_camera_complete()
            
        except Exception as e:
            print(f"FLIR采集线程错误: {e}")
            RUNNING.value = 0
    
    def _thermal_capture_worker(self):
        """红外相机采集工作线程 - 修复版本"""
        try:
            # 启动红外相机采集
            if self.thermal_cam.start_capture():
                # 等待采集和处理完全完成
                self.thermal_cam.wait_for_completion()
                print("红外相机数据处理完成")
            
            # 标记红外相机完成（包括处理）
            self._mark_camera_complete()
            
        except Exception as e:
            print(f"红外相机采集线程错误: {e}")

    def _mark_camera_complete(self):
        """标记相机完成采集"""
        with self.status_lock:
            self.completed_cameras += 1
            print(f"相机完成采集进度: {self.completed_cameras}/2")
            if self.completed_cameras >= 2:  # 两个相机都完成
                print("所有相机采集完成！")
                self.capture_complete_event.set()
    
    def _flir_data_processor(self):
        """FLIR数据处理线程 - 修复版本，参考三相机脚本"""
        print("FLIR数据处理线程启动...")
        images = {}
        exposure_times = {}
        timestamps = {}
        
        while True:
            try:
                # 使用与三相机脚本相同的超时时间
                data = self.flir_queue.get(timeout=5)  # 改回5秒超时
                
                if data is None:  # 结束信号
                    break
                
                # 存储数据
                idx = data['index']
                images[idx] = data['data']
                exposure_times[idx] = data['exposure_time']
                timestamps[idx] = data['timestamp']
                
                self.flir_queue.task_done()
                
            except queue.Empty:
                if self.capture_complete_event.is_set():
                    break
                continue
    
        # 处理和保存数据
        if images:
            self._save_flir_data(images, exposure_times, timestamps)
        else:
            print("没有FLIR数据需要保存")

    
    def _thermal_data_processor(self):
        """红外数据处理线程 - 恢复实现"""
        pass

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
        timestamp_list = np.array([timestamps[i] for i in valid_indices])
        
        self.flir._save_data(image_array, exposure_array, timestamp_list, self.save_path)
        print(f"已保存 {len(valid_indices)} 张FLIR图像")
    
    def cleanup(self):
        try:
            print("开始清理异步控制器资源...")
            
            # 停止所有采集
            RUNNING.value = 0
            # 发送结束信号给处理线程
            try:
                self.flir_queue.put(None)
            except:
                pass
            
            # 设置采集完成事件，确保所有等待的线程能够退出
            if not self.capture_complete_event.is_set():
                self.capture_complete_event.set()
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=True)  # 等待所有任务完成
                except Exception as e:
                    print(f"关闭线程池时出错: {e}")
                
            if self.thermal_cam:
                try:
                    self.thermal_cam.cleanup()
                except Exception as e:
                    print(f"清理红外相机时出错: {e}")
        
            if self.flir:
                try:
                    self.flir.cleanup()
                    print("FLIR相机资源已清理")
                except Exception as e:
                    print(f"清理FLIR相机时出错: {e}")

        except Exception as e:
            print(f"清理资源时出错: {e}")


def main():
    """主函数 - Xavier NX优化版实时优先级支持"""
    print("=== 双相机同步采集系统 (FLIR+红外) (Xavier NX优化) ===")
    
    # 检查系统实时权限
    has_rt_perms = print_system_info()
    
    if not has_rt_perms:
        print("建议以root权限运行以获得最佳性能: sudo python3 sync_2_fr.py")
        print("继续运行（性能可能受限）...")
    
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