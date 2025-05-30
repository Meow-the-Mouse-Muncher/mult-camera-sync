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

class CameraStar:
    def __init__(self):
        """初始化相机参数"""
        self.handle = 0
        self.isConnect = False
        self.iplist = []
        self.sframe = []
        
        # 图像相关参数
        self.imgsize = [HEIGHT, WIDTH]
        self.gray = (c_uint16 * WIDTH * HEIGHT)()
        self.buf = (c_uint8 * 1024)()
        self.rgb = (c_uint8 * 3 * WIDTH * HEIGHT)()
        
        # 采集相关参数
        self.frame_buffer = []  # 动态帧缓存
        self.is_capturing = False
        self.target_count = 0
        self.captured_count = 0
        
        # 处理线程
        self.process_thread = None
        self.mutex = threading.Lock()
        
        # IP地址数组初始化
        self.ipaddr = []
        for i in range(32):
            ip_addr = T_IPADDR()
            self.ipaddr.append(ip_addr)
        self.ip_addr_array = (T_IPADDR * 32)(*self.ipaddr)
        
        # 创建保存目录结构
        self.base_dir = BASE_DIR
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
        # 初始化SDK
        sdk_init()
        sdk_setIPAddrArray(self.ip_addr_array)
        
        # 初始化帧处理
        self.glbFrame = Frame()
        self.sizeFrame = 32 + WIDTH * HEIGHT * 2
        
        # 设置回调函数
        VIDEOCALLBACKFUNC = CFUNCTYPE(c_int, c_void_p, c_void_p)
        self.callback = VIDEOCALLBACKFUNC(self.frame_callback)

    def frame_callback(self, frame, this):
        """帧数据回调处理，只进行数据拷贝"""
        if not self.is_capturing:
            return 0
            
        if self.captured_count >= self.target_count:
            return 0
            
        bytebuf = string_at(frame, self.sizeFrame)
        # 直接拷贝到对应位置的缓存中
        memmove(addressof(self.frame_buffer[self.captured_count]), bytebuf, self.sizeFrame)
        self.captured_count += 1
        
        if self.captured_count >= self.target_count:
            self.is_capturing = False
            # 启动处理线程
            self.process_thread = threading.Thread(target=self.process_frames)
            self.process_thread.start()
        return 0
        
    def process_frames(self):
        """在单独的线程中处理所有帧"""
        frames_to_process = min(self.captured_count, self.target_count)
        
        # 创建以时间戳命名的子目录
        curtime = datetime.now().strftime('%Y-%m-%d_%H.%M.%S')
        save_dir = os.path.join(self.base_dir, curtime)
        os.makedirs(save_dir)
        
        # 保存采集参数信息
        with open(os.path.join(save_dir, 'capture_info.txt'), 'w') as f:
            f.write(f"采集时间: {curtime}\n")
            f.write(f"采集帧率: {FPS} fps\n")
            f.write(f"温度段: {TEMP_SEGMENT}\n")
            f.write(f"图像尺寸: {WIDTH}x{HEIGHT}\n")
            f.write(f"实际采集帧数: {frames_to_process}\n")
        
        for i in range(frames_to_process):
            frame = self.frame_buffer[i]
            # 保存图像文件名
            gray_path = os.path.join(save_dir, f'gray_{i:04d}.jpg')
            rgb_path = os.path.join(save_dir, f'rgb_{i:04d}.jpg')
            
            # 使用当前帧而不是self.sframe
            sdk_frame2gray(byref(frame), byref(self.gray))
            gray_array = np.frombuffer(self.gray, dtype=np.uint16)
            gray_array = gray_array.reshape((HEIGHT, WIDTH))
            gray_array = ((gray_array - gray_array.min()) * (255.0 / (gray_array.max() - gray_array.min()))).astype(np.uint8)
            gray_img = Image.fromarray(gray_array)
            gray_img.save(gray_path)
            
            # 转换为RGB图并保存
            sdk_gray2rgb(byref(self.gray), byref(self.rgb), self.imgsize[1], self.imgsize[0], 0, 1)
            rgb_pathbytes = str.encode(rgb_path)
            sdk_saveframe2jpg(rgb_pathbytes, frame, self.rgb)
            
        print(f"已完成 {frames_to_process} 张图像的处理")
        
    def start_capture(self, count=None):
        """开始采集指定张数的图像"""
        if not self.isConnect:
            print("相机未连接")
            return False
            
        # 使用配置文件中的参数
        count = count or CAPTURE_COUNT
        time.sleep(0.1)
        
        # 清空并重新分配帧缓存
        self.frame_buffer.clear()
        for _ in range(count):
            frame = Frame()
            self.frame_buffer.append(frame)
            
        self.target_count = count   
        self.captured_count = 0
        self.is_capturing = True
        print(f"开始采集 {count} 张图像")
        return True
        
    def stop_capture(self):
        """停止自动采集"""
        self.is_capturing = False
        if self.process_thread:
            self.process_thread.join()
        print(f"已停止采集，共采集了 {self.captured_count} 张图像")
        
    def connect_camera(self, ip_address, port=None):
        """连接相机"""
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
        time.sleep(1)
        
        self.isConnect = sdk_isconnect(self.handle)
        return self.isConnect

    def set_temp_segment(self, index):
        """设置温度段"""
        if self.isConnect:
            sdk_tempseg_sel(self.handle, index)
            
    def calibration(self):
        """快门补偿"""
        if self.isConnect:
            sdk_calibration(self.handle)

    def grab_image(self):
        """抓取图像并保存灰度图和RGB图"""
        if not self.isConnect:
            print("相机未连接")
            return False
            
        curtime = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%f')[:-3]
        gray_path = f'{self.grabdir}/gray_{self.handle}_{curtime}.jpg'
        rgb_path = f'{self.grabdir}/rgb_{self.handle}_{curtime}.jpg'
        
        if hasattr(self, 'sframe') and self.sframe:
            # 转换为灰度图
            sdk_frame2gray(byref(self.sframe), byref(self.gray))
            
            # 保存灰度图
            gray_array = np.frombuffer(self.gray, dtype=np.uint16)
            gray_array = gray_array.reshape((HEIGHT, WIDTH))
            gray_array = ((gray_array - gray_array.min()) * (255.0 / (gray_array.max() - gray_array.min()))).astype(np.uint8)
            gray_img = Image.fromarray(gray_array)
            gray_img.save(gray_path)
            print(f"灰度图已保存至: {gray_path}")
            
            # 转换为RGB并保存
            sdk_gray2rgb(byref(self.gray), byref(self.rgb), self.imgsize[1], self.imgsize[0], 0, 1)
            rgb_pathbytes = str.encode(rgb_path)
            sdk_saveframe2jpg(rgb_pathbytes, self.sframe, self.rgb)
            print(f"RGB图像已保存至: {rgb_path}")
            
            return True
        return False
        
    def close(self):
        """关闭相机连接"""
        if self.isConnect:
            sdk_stop(self.handle)
        sdk_quit()

def main():
    camera = CameraStar()
    
    result = camera.connect_camera(CAMERA_IP, CAMERA_PORT)
    if result:
        print("相机连接成功")
    else:   
        print("相机连接失败")
    # print("相机连接成功")
    
    camera.set_temp_segment(TEMP_SEGMENT)
    camera.calibration()
    
    camera.start_capture()  # 使用配置文件中的默认值
    
    while camera.is_capturing:
        time.sleep(0.1)
        print(f"已采集 {camera.captured_count} 张图像")
        
    if camera.process_thread:
        camera.process_thread.join()
        
    camera.close()
    # else:
    #     print("相机连接失败")

if __name__ == "__main__":
    main()