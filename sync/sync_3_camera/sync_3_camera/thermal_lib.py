from camera_inf import *
import time
import os
import numpy as np
from datetime import datetime
from ctypes import *
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from config import *
from PIL import Image

# 全局SDK状态管理
_sdk_initialized = False
_sdk_lock = threading.Lock()

def ensure_sdk_initialized():
    """确保SDK已初始化"""
    global _sdk_initialized
    with _sdk_lock:
        if not _sdk_initialized:
            sdk_init()
            _sdk_initialized = True
            print("红外SDK已初始化")

def ensure_sdk_cleanup():
    """确保SDK已清理"""
    global _sdk_initialized
    with _sdk_lock:
        if _sdk_initialized:
            try:
                sdk_quit()
                _sdk_initialized = False
                print("红外SDK已清理")
            except Exception as e:
                print(f"清理红外SDK时出错: {e}")

class ThermalCamera:
    def __init__(self):
        """初始化相机参数"""
        self.handle = 0
        self.is_connected = False
        self.last_callback_time = None
        
        # 图像相关参数
        self.imgsize = [THERMAL_HEIGHT, THERMAL_WIDTH]
        self.gray = (c_uint16 * THERMAL_WIDTH * THERMAL_HEIGHT)()
        self.buf = (c_uint8 * 1024)()
        self.rgb = (c_uint8 * 3 * THERMAL_WIDTH * THERMAL_HEIGHT)()
        
        # 采集相关参数
        self.frame_buffer = []
        self.is_capturing = False
        self.target_count = 0
        self.captured_count = 0
        
        # 异步处理
        self.executor = ThreadPoolExecutor(max_workers=3)  # 增加worker数量：1个拷贝，2个图像处理
        self.frame_queue = queue.Queue(maxsize=200)  # 帧数据队列
        self.copy_future = None
        self.process_future = None
        self.is_processing = False
        self.mutex = threading.Lock()
        
        # IP地址初始化
        self.ipaddr = []
        for i in range(32):
            ip_addr = T_IPADDR()
            self.ipaddr.append(ip_addr)
        self.ip_addr_array = (T_IPADDR * 32)(*self.ipaddr)
        
        # 创建保存目录
        self.base_dir = BASE_DIR
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
        # 初始化SDK（使用全局管理）
        ensure_sdk_initialized()
        sdk_setIPAddrArray(self.ip_addr_array)
        
        # 初始化帧处理
        self.frame = Frame()
        self.frame_size = 32 + THERMAL_WIDTH * THERMAL_HEIGHT * 2
        
        # 设置回调函数
        VIDEOCALLBACKFUNC = CFUNCTYPE(c_int, c_void_p, c_void_p)
        self.callback = VIDEOCALLBACKFUNC(self.frame_callback)

    def frame_callback(self, frame, this):
        """帧数据回调处理 - 修复版本，避免队列不匹配"""
        if not self.is_capturing or self.captured_count >= self.target_count:
            return 0
        
        try:
            # 直接将frame指针和索引放入队列，避免在回调中进行数据拷贝
            # 这样可以最大限度减少回调函数的执行时间
            frame_index = self.captured_count
            self.frame_queue.put_nowait((frame, frame_index))
            # 只有成功放入队列后才增加计数
            self.captured_count += 1
            if self.captured_count >= self.target_count:
                self.is_capturing = False
                
        except queue.Full:
            # 性能优化：队列满时不打印警告，避免影响回调速度
            # 如果队列满了，不增加captured_count，这样保证队列任务数和计数匹配
            pass
            
        return 0
    
    def connect(self, ip_address=None, port=None):
        """连接相机"""
        ip_address = ip_address or THERMAL_CAMERA_IP
        port = port or THERMAL_CAMERA_PORT
        
        if port is None:
            str_iplist = ip_address.split('.')
            port = 30005 + 100 * int(str_iplist[3])
            
        ip = T_IPADDR()
        str_ip_as_bytes = str.encode(ip_address)
        
        for i in range(len(str_ip_as_bytes)):
            ip.IPAddr[i] = str_ip_as_bytes[i]
        ip.DataPort = port
        ip.isValid = 1
        
        sdk_creat_connect(self.handle, ip, self.callback, None)
        time.sleep(1)  # 等待连接建立
        self.is_connected = sdk_isconnect(self.handle)
        print(f"红外相机连接状态: {self.is_connected}")
        # 不使用sdk_isconnect的返回值判断连接状态
        self.is_connected = True
        print(f"已尝试连接红外相机: {ip_address}:{port}")
        return True
    def configure_camera(self, temp_segment, frame_count, save_path=None):
            """配置红外相机
            Args:
                temp_segment: 温度段
                frame_count: 需要采集的总帧数 (第一帧将被丢弃，实际保存 frame_count - 1 帧)
                save_path: 保存路径
            """
            if not self.is_connected:
                print("相机未连接，无法配置")
                return False
            
            if frame_count < 0:
                print("请求采集的帧数不能为负")
                return False
                
            # 设置温度段和校准
            self.set_temp_segment(temp_segment)
            self.calibration()
            self.calisw(1)  # 设置自动校正开关
            
            # 分配帧缓存
            self.frame_buffer.clear()
            for _ in range(frame_count): # 仍然分配 frame_count 个缓存，因为都需要采集
                frame = Frame()
                self.frame_buffer.append(frame)
            
            self.target_count = frame_count # target_count 是计划采集的总帧数
            
            # 更新保存路径
            if save_path:
                self.base_dir = save_path
            
            if frame_count > 0:
                frames_to_be_saved = max(0, frame_count - 1)
                print(f"红外相机配置成功。将尝试采集 {frame_count} 帧，预计保存 {frames_to_be_saved} 帧 (丢弃第一帧后)。")
            else: # frame_count == 0
                print(f"红外相机配置成功。请求采集 0 帧，将不保存任何图像。")
            return True
    def start_capture(self):
        """开始采集图像 - 异步版本"""
        if not self.is_connected:
            print("相机未连接")
            return False
        
        if not self.frame_buffer:
            print("未配置帧缓存")
            return False
        
        # 清空队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
                # 注意：这里不调用task_done，因为这些是旧的任务
            except queue.Empty:
                break
        
        # 重置状态
        self.captured_count = 0
        self.is_capturing = True
        self.is_processing = False
        
        # 重置futures
        self.copy_future = None
        self.process_future = None
        
        # 启动异步数据拷贝 - 在设置is_capturing=True之后
        self.copy_future = self.executor.submit(self._async_copy_worker)
        
        print(f"开始采集 {self.target_count} 张图像")
        return True
    
    def _async_copy_worker(self):
        """异步数据拷贝工作线程 - 优化版本，移除调试信息"""
        processed_count = 0
        max_wait_time = 30  # 最大等待时间30秒
        start_time = time.time()
        
        # 等待采集真正开始或有数据进入队列
        while self.is_capturing and self.frame_queue.empty() and (time.time() - start_time) < 5:
            time.sleep(0.1)  # 等待采集开始
        
        while self.is_capturing or not self.frame_queue.empty():
            try:
                # 从队列获取frame指针和索引
                frame_ptr, frame_index = self.frame_queue.get(timeout=1.0)
                
                # 在工作线程中进行数据拷贝，避免阻塞回调
                try:
                    bytebuf = string_at(frame_ptr, self.frame_size)
                    frame_data = bytes(bytebuf)  # 创建数据副本
                    
                    # 拷贝到frame_buffer
                    with self.mutex:
                        if frame_index < len(self.frame_buffer):
                            memmove(addressof(self.frame_buffer[frame_index]), frame_data, len(frame_data))
                            processed_count += 1
                            
                except Exception as e:
                    # 性能优化：只记录严重错误，避免频繁打印
                    pass
                finally:
                    # 确保无论成功失败都调用task_done
                    self.frame_queue.task_done()
                
            except queue.Empty:
                # 如果队列空了但还在采集，继续等待
                if self.is_capturing:
                    continue
                # 如果不在采集且队列空了，检查是否超时
                if time.time() - start_time > max_wait_time:
                    # 数据拷贝线程等待超时，退出
                    break
                continue
            except Exception as e:
                # 性能优化：减少错误打印
                # 如果从队列获取数据成功但处理失败，也需要调用task_done
                try:
                    self.frame_queue.task_done()
                except:
                    pass
        
        # 数据拷贝线程完成，处理了指定数量的帧
    
    def wait_for_completion(self):
        """等待采集和处理完成 - 优化版本"""
        # 等待采集完成，简化进度显示
        wait_start_time = time.time()
        
        while self.is_capturing:
            time.sleep(0.5)  # 每0.5秒检查一次
            
            # 检查是否超时 (30秒)
            if time.time() - wait_start_time > 30:
                print("红外相机采集超时！强制停止")
                self.is_capturing = False
                break
        
        print(f"红外相机采集完成: {self.captured_count}/{self.target_count}")
        # 红外相机完成后，设置标志停止事件相机
        print("设置停止标志，准备停止事件相机...")
        ACQUISITION_FLAG.value = 1  # 设置为1来停止事件相机
        
        # 等待数据拷贝完成
        if self.copy_future:
            try:
                self.copy_future.result(timeout=10)  # 10秒超时
            except Exception as e:
                print(f"数据拷贝超时或出错: {e}")
        
        # 等待队列处理完成，使用join方法而不是检查队列大小
        try:
            # 使用join方法等待所有任务完成，设置超时
            self.frame_queue.join()  # 这里会等待所有put的项目都被task_done
        except Exception as e:
            print(f"队列join出错: {e}")
            # 如果join失败，清空剩余队列
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.task_done()
                except:
                    break
        
        # 异步开始图像处理
        if not self.is_processing and self.captured_count > 0:
            print("开始处理红外图像...")
            self.is_processing = True
            self.process_future = self.executor.submit(self.process_frames)
        
        # 等待处理完成
        if self.process_future:
            try:
                result = self.process_future.result(timeout=120)  # 增加到120秒超时
                print(f"红外图像处理完成，处理了 {result} 张图像")
            except TimeoutError:
                print("红外图像处理超时！")
            except Exception as e:
                print(f"图像处理出错: {e}")

    def process_frames(self):
        """处理采集的帧 - 优化版本，支持并行处理"""
        frames_actually_captured = min(self.captured_count, self.target_count)
        
        # 使用主程序传入的保存路径
        save_dir = os.path.join(self.base_dir, 'thermal')
        os.makedirs(save_dir, exist_ok=True)
        
        num_frames_to_save = 0
        if frames_actually_captured <= 1:
            print(f"实际采集 {frames_actually_captured} 帧。按要求丢弃第一帧后，无图像可保存。")
            return
        else:
            num_frames_to_save = frames_actually_captured - 1
        
        print(f"开始处理 {num_frames_to_save} 张红外图像...")
        
        # 批量处理以提高效率
        batch_size = 10  # 每批处理10张图像
        process_start_time = time.time()
        processed_count = 0
        
        for batch_start in range(0, num_frames_to_save, batch_size):
            batch_end = min(batch_start + batch_size, num_frames_to_save)
            batch_indices = list(range(batch_start, batch_end))
            
            # 并行处理当前批次
            futures = []
            for i in batch_indices:
                future = self.executor.submit(self._process_single_frame, i, save_dir)
                futures.append((i, future))
            
            # 等待当前批次完成
            for i, future in futures:
                try:
                    success = future.result(timeout=30)  # 30秒超时
                    if success:
                        processed_count += 1
                except Exception as e:
                    # 性能优化：只记录处理失败的关键错误
                    pass
        
        total_time = time.time() - process_start_time
        print(f"红外图像处理完成! 共处理 {processed_count}/{num_frames_to_save} 张图像")
        return processed_count  # 返回处理的图像数量
    
    def _process_single_frame(self, frame_index, save_dir):
        """处理单个帧的工作函数"""
        try:
            # 要保存的帧在原始捕获序列中是第 frame_index+1 帧 (跳过第0帧)
            frame_buffer_index = frame_index + 1 
            
            if frame_buffer_index >= len(self.frame_buffer):
                # 性能优化：减少错误打印，只返回False
                return False
            
            frame = self.frame_buffer[frame_buffer_index]
            gray_path = os.path.join(save_dir, f'gray_{frame_index:04d}.jpg')
            
            # 转换为灰度图像
            local_gray = (c_uint16 * THERMAL_WIDTH * THERMAL_HEIGHT)()
            sdk_frame2gray(byref(frame), byref(local_gray))
            gray_array = np.frombuffer(local_gray, dtype=np.uint16)
            gray_array = gray_array.reshape((THERMAL_HEIGHT, THERMAL_WIDTH))
            
            # 归一化到0-255范围
            min_val = gray_array.min()
            max_val = gray_array.max()
            if max_val == min_val:  # 防止除以零
                gray_array_normalized = np.zeros_like(gray_array, dtype=np.uint8)
            else:
                gray_array_normalized = ((gray_array - min_val) * (255.0 / (max_val - min_val))).astype(np.uint8)
            
            # 保存图像
            gray_img = Image.fromarray(gray_array_normalized)
            gray_img.save(gray_path, optimize=True, quality=95)  # 添加质量参数
            
            return True
            
        except Exception as e:
            # 性能优化：减少错误打印和traceback
            return False

    def stop_capture(self):
        """停止采集"""
        self.is_capturing = False
        if self.process_future:
            self.process_future.result()
        # 停止采集，共采集了指定数量张图像

    def set_temp_segment(self, index):
        """设置温度段"""
        if self.is_connected:
            sdk_tempseg_sel(self.handle, index)

    def calibration(self):
        """快门补偿"""
        if self.is_connected:
            sdk_calibration(self.handle)
            
    def calisw(self, sw):
        """设置自动校正开关"""
        if self.is_connected:
            sdk_setcaliSw(self.handle, sw)

    def cleanup(self):
        """清理相机资源 - 优化版本"""
        print("正在清理红外相机资源...")
        
        # 停止采集
        self.is_capturing = False
        
        # 等待并清理线程池
        if hasattr(self, 'executor') and self.executor:
            try:
                # 等待正在执行的任务完成
                if self.copy_future and not self.copy_future.done():
                    try:
                        self.copy_future.result(timeout=5)
                    except Exception:
                        pass
                if self.process_future and not self.process_future.done():
                    try:
                        self.process_future.result(timeout=10)
                    except Exception:
                        pass
                    
                # 关闭线程池
                self.executor.shutdown(wait=True)
            except Exception as e:
                # 清理线程池时可能出错，但不影响主要流程
                pass
        
        # 清空队列
        try:
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.task_done()
                except:
                    break
        except:
            pass
        
        # 断开相机连接
        if self.is_connected:
            try:
                sdk_stop(self.handle)
                self.is_connected = False
            except Exception as e:
                # 停止相机时出错，但不影响清理流程
                pass
        
        # 注意：不要调用 sdk_quit()，因为这是全局的，可能影响下次初始化
        # 只在程序完全退出时才调用 sdk_quit()
            
        print("红外相机资源清理完成")
