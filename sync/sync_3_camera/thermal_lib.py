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
                frame_count: 需要采集的帧数
                save_path: 保存路径
            """
            if not self.is_connected:
                print("相机未连接，无法配置")
                return False
                
            # 设置温度段和校准
            self.set_temp_segment(temp_segment)
            self.calibration()
            
            # 分配帧缓存
            self.frame_buffer.clear()
            for _ in range(frame_count):
                frame = Frame()
                self.frame_buffer.append(frame)
            
            self.target_count = frame_count
            
            # 更新保存路径
            if save_path:
                self.base_dir = save_path
            
            print("红外相机配置成功")
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
        frames_to_process = min(self.captured_count, self.target_count)
        
        # 使用主程序传入的保存路径
        save_dir = os.path.join(self.base_dir, 'thermal')
        os.makedirs(save_dir, exist_ok=True)
        
        # 保存采集信息
        with open(os.path.join(save_dir, 'capture_info.txt'), 'w') as f:
            f.write(f"采集时间: {time.strftime('%Y-%m-%d_%H.%M.%S')}\n")
            f.write(f"采集帧率: {THERMAL_FPS} fps\n")
            f.write(f"温度段: {THERMAL_TEMP_SEGMENT}\n")
            f.write(f"图像尺寸: {THERMAL_WIDTH}x{THERMAL_HEIGHT}\n")
            f.write(f"实际采集帧数: {frames_to_process}\n")
        
        for i in range(frames_to_process):
            frame = self.frame_buffer[i]
            gray_path = os.path.join(save_dir, f'gray_{i:04d}.jpg')
            rgb_path = os.path.join(save_dir, f'rgb_{i:04d}.jpg')
            
            sdk_frame2gray(byref(frame), byref(self.gray))
            gray_array = np.frombuffer(self.gray, dtype=np.uint16)
            gray_array = gray_array.reshape((THERMAL_HEIGHT, THERMAL_WIDTH))
            gray_array = ((gray_array - gray_array.min()) * (255.0 / (gray_array.max() - gray_array.min()))).astype(np.uint8)
            gray_img = Image.fromarray(gray_array)
            gray_img.save(gray_path)
            
            # sdk_gray2rgb(byref(self.gray), byref(self.rgb), self.imgsize[1], self.imgsize[0], 0, 1)
            # rgb_pathbytes = str.encode(rgb_path)
            # sdk_saveframe2jpg(rgb_pathbytes, frame, self.rgb)
            
        print(f"已完成 {frames_to_process} 张图像的处理")

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

    def wait_for_completion(self):
        """等待采集和处理完成"""
        # 等待采集完成
        while self.is_capturing:
            time.sleep(0.1)
            print(f"红外相机已采集 {self.captured_count}/{self.target_count} 张图像")
        
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
