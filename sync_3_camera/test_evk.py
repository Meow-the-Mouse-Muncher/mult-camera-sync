import os
import time
import signal
import serial
import sys
from multiprocessing import Value
from event_lib import EventCamera, ensure_dir
from config import *
sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
from metavision_core.event_io.raw_reader import RawReader

# 全局控制变量
RUNNING = Value('i', 1)
ACQUISITION_FLAG = Value('i', 0)

class EVK4Tester:
    def __init__(self, save_path):
        self.save_path = save_path
        self.event_cam = None
        self.recording_duration = 5  # 录制时长（秒）
        
    def signal_handler(self, sig, frame):
        """处理Ctrl+C信号"""
        print('\n正在停止录制...')
        RUNNING.value = 0
        ACQUISITION_FLAG.value = 1
        sys.exit(0)
    def send_pulse_command(self, num_pulses, frequency):  
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
        
    def setup_camera(self):
        """初始化事件相机"""
        print("=== EVK4事件相机测试 ===")
        
        # 创建保存目录
        ensure_dir(self.save_path)
        
        # 初始化事件相机
        self.event_cam = EventCamera(num=0, path=self.save_path)
        
        # 配置相机
        print("正在配置事件相机...")
        if not self.event_cam.config_prophesee():
            print("事件相机配置失败")
            return False
            
        print("事件相机配置成功")
        return True
        
    def start_recording_test(self):
        """开始录制测试"""
        if not self.event_cam:
            print("事件相机未初始化")
            return False
            
        print(f"开始录制事件流，持续 {self.recording_duration} 秒...")
        print("请在此期间发送触发信号进行测试")
        
        # 启动录制
        start_time = time.time()
        
        # 重置控制标志
        RUNNING.value = 1
        ACQUISITION_FLAG.value = 0
        
        # 开始录制（在单独线程中）
        import threading
        recording_thread = threading.Thread(target=self.event_cam.start_recording)
        recording_thread.daemon = True
        recording_thread.start()
        self.send_pulse_command(30,20)
        # 等待指定时间或手动停止
        try:
            while time.time() - start_time < self.recording_duration:
                if not RUNNING.value:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n用户中断录制")
            
        # 停止录制
        print("停止录制...")
        self.event_cam.stop_recording()
        ACQUISITION_FLAG.value = 1
        RUNNING.value = 0
        
        # 等待录制线程结束
        recording_thread.join(timeout=5)
        
        print(f"录制完成，数据保存至: {self.event_cam.outputpath}")
        return True
        
    def check_triggers(self):
        """检查触发信号"""
        if not self.event_cam:
            print("事件相机未初始化")
            return
            
        print("\n=== 检查触发信号 ===")
        
        # 检查raw文件是否存在
        if not os.path.exists(self.event_cam.outputpath):
            print(f"录制文件不存在: {self.event_cam.outputpath}")
            return
            
        # 获取文件大小
        file_size = os.path.getsize(self.event_cam.outputpath)
        print(f"录制文件大小: {file_size/1024/1024:.2f} MB")
        triggers = None
        with RawReader(str(os.path.join(self.save_path,"event","event.raw")), do_time_shifting=False) as ev_data:
            while not ev_data.is_done():
                ev_data.load_n_events(1000000)
            triggers = ev_data.get_ext_trigger_events()

        if len(triggers) > 0:
            print(f"总触发信号数量: {len(triggers)}")
            triggers = triggers[triggers['p'] == 1].copy()
            print(f"需要保存触发信号数量: {len(triggers)}")
        else:
            print("未检测到触发信号")
        
        # 分析触发信号
        print("正在分析触发信号...")
        try:
            triggers = self.event_cam.prophesee_tirgger_found()
            if triggers is not None and len(triggers) > 0:
                print(f"成功检测到 {len(triggers)} 个触发信号")
            else:
                print("未检测到有效触发信号")
                
        except Exception as e:
            print(f"触发信号分析失败: {e}")
            
    def cleanup(self):
        """清理资源"""
        if self.event_cam and self.event_cam.device:
            try:
                self.event_cam.device.stop()
                print("事件相机设备已停止")
            except:
                pass
                
def main():
    """主测试函数"""
    # 创建保存目录
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.join("./test_data", timestamp)
    
    # 创建测试器
    tester = EVK4Tester(save_path)

    
    # 注册信号处理
    signal.signal(signal.SIGINT, tester.signal_handler)
    
    try:
        # 初始化相机
        if not tester.setup_camera():
            return False
            
        # 开始录制测试
        if not tester.start_recording_test():
            return False
            
        # 检查触发信号
        tester.check_triggers()
        
        print("\n=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return False
    finally:
        tester.cleanup()

if __name__ == "__main__":
    success = main()
    if success:
        print("测试成功完成")
    else:
        print("测试失败")
    sys.exit(0 if success else 1)