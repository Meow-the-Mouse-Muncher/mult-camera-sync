from camera_inf import *
import time
import os
import numpy as np
from datetime import datetime
from ctypes import *
from queue import Queue
import threading
from config import *
from PIL import Image

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
        
        # 处理线程
        self.process_thread = None
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
            
        # 初始化SDK
        sdk_init()
        sdk_setIPAddrArray(self.ip_addr_array)
        
        # 初始化帧处理
        self.frame = Frame()
        self.frame_size = 32 + THERMAL_WIDTH * THERMAL_HEIGHT * 2
        
        # 设置回调函数
        VIDEOCALLBACKFUNC = CFUNCTYPE(c_int, c_void_p, c_void_p)
        self.callback = VIDEOCALLBACKFUNC(self.frame_callback)
        
        self.is_processing = False  # 添加处理状态标志

    def frame_callback(self, frame, this):
        """帧数据回调处理"""
        if not self.is_capturing:
            return 0
            
        if self.captured_count >= self.target_count:
            return 0
            
        bytebuf = string_at(frame, self.frame_size)
        with self.mutex:
            memmove(addressof(self.frame_buffer[self.captured_count]), bytebuf, self.frame_size)
            self.captured_count += 1
        
        if self.captured_count >= self.target_count:
            print(f"已采集 {self.captured_count} 张图像")
            print("开始处理图像...")
            self.is_capturing = False
            self.is_processing = True  # 标记开始处理
            self.process_thread = threading.Thread(target=self.process_frames)
            self.process_thread.start()
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
        """开始采集图像"""
        if not self.is_connected:
            print("相机未连接")
            return False
        
        if not self.frame_buffer:
            print("未配置帧缓存")
            return False
            
        self.captured_count = 0
        self.is_capturing = True
        self.is_processing = False  # 重置处理状态
        print(f"开始采集 {self.target_count} 张图像")
        return True

    def process_frames(self):
        """处理采集的帧"""
        frames_actually_captured = min(self.captured_count, self.target_count)
        
        # 使用主程序传入的保存路径
        save_dir = os.path.join(self.base_dir, 'thermal')
        os.makedirs(save_dir, exist_ok=True)
        
        num_frames_to_save = 0
        if frames_actually_captured <= 1:
            print(f"实际采集 {frames_actually_captured} 帧。按要求丢弃第一帧后，无图像可保存。")
            num_frames_to_save = 0
        else:
            num_frames_to_save = frames_actually_captured - 1
        
        # # 保存采集信息
        # with open(os.path.join(save_dir, 'capture_info.txt'), 'w') as f:
        #     f.write(f"采集时间: {time.strftime('%Y-%m-%d_%H.%M.%S')}\n")
        #     f.write(f"采集帧率: {THERMAL_FPS} fps\n")
        #     f.write(f"温度段: {THERMAL_TEMP_SEGMENT}\n")
        #     f.write(f"图像尺寸: {THERMAL_WIDTH}x{THERMAL_HEIGHT}\n")
        #     f.write(f"请求采集总帧数: {self.target_count}\n")
        #     f.write(f"实际回调捕获帧数: {self.captured_count}\n")
        #     f.write(f"用于处理的捕获帧数: {frames_actually_captured}\n")
        #     f.write(f"实际保存帧数 (丢弃第一帧后): {num_frames_to_save}\n")
        
        if num_frames_to_save > 0:
            for i in range(num_frames_to_save):
                # 要保存的帧在原始捕获序列中是第 i+1 帧 (跳过第0帧)
                frame_buffer_index = i + 1 
                
                frame = self.frame_buffer[frame_buffer_index]
                gray_path = os.path.join(save_dir, f'gray_{i:04d}.jpg') # 保存的文件名从 0 开始
                # rgb_path = os.path.join(save_dir, f'rgb_{i:04d}.jpg') # 保存的文件名从 0 开始
                
                sdk_frame2gray(byref(frame), byref(self.gray))
                gray_array = np.frombuffer(self.gray, dtype=np.uint16)
                gray_array = gray_array.reshape((THERMAL_HEIGHT, THERMAL_WIDTH))
                
                min_val = gray_array.min()
                max_val = gray_array.max()
                if max_val == min_val: # 防止除以零
                    gray_array_normalized = np.zeros_like(gray_array, dtype=np.uint8)
                else:
                    gray_array_normalized = ((gray_array - min_val) * (255.0 / (max_val - min_val))).astype(np.uint8)
                
                gray_img = Image.fromarray(gray_array_normalized)
                gray_img.save(gray_path)
                
                # sdk_gray2rgb(byref(self.gray), byref(self.rgb), self.imgsize[1], self.imgsize[0], 0, 1)
                # rgb_pathbytes = str.encode(rgb_path)
                # sdk_saveframe2jpg(rgb_pathbytes, frame, self.rgb)
            
        print(f"已完成 {num_frames_to_save} 张图像的处理和保存。")

    def stop_capture(self):
        """停止采集"""
        self.is_capturing = False
        if self.process_thread:
            self.process_thread.join()
        print(f"已停止采集，共采集了 {self.captured_count} 张图像")

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

    def wait_for_completion(self):
        """等待采集和处理完成"""
        # 等待采集完成
        while self.is_capturing:
            # time.sleep(0.04)
            print(f"红外相机已采集 {self.captured_count}/{self.target_count} 张图像")
            pass
        
        # 等待处理完成
        if self.is_processing and self.process_thread:
            print("等红外图像处理完成...")
            self.process_thread.join()
            self.is_processing = False
            print("红外图像处理完成")

    def cleanup(self):
        """清理相机资源"""
        if self.is_connected:
            sdk_stop(self.handle)
        sdk_quit()
