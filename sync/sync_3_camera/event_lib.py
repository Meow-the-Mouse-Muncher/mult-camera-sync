import sys
import os
import numpy as np
from config import *

sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device
from metavision_hal import I_EventTrailFilterModule

class EventCamera:
    """Prophesee事件相机控制类"""
    
    def __init__(self, num, path):
        """初始化事件相机
        Args:
            num (int): 相机编号
            path (str): 数据保存路径
        """
        self.num = num
        self.width = PROPHESEE_ROI_X1 - PROPHESEE_ROI_X0
        self.height = PROPHESEE_ROI_Y1 - PROPHESEE_ROI_Y0
        self.path = path
        self.outputpath = os.path.join(path, 'event', 'event.raw')
        self.ieventstream = None
        self.device = None

    def prophesee_tirgger_found(self, polarity: int = 0, do_time_shifting=False):
        """查找触发信号并保存时间戳
        Args:
            polarity (int): 触发极性，0为正，1为负
            do_time_shifting (bool): 是否进行时间偏移
        Returns:
            triggers: 触发信号数据
        """
        triggers = None
        with RawReader(str(self.outputpath), do_time_shifting=do_time_shifting) as ev_data:
            while not ev_data.is_done():
                ev_data.load_n_events(1000000)
            triggers = ev_data.get_ext_trigger_events()
            
        if len(triggers) > 0:
            print(f"总触发信号数量: {len(triggers)}")

            if polarity in (0, 1):
                triggers = triggers[triggers['p'] == polarity].copy()
            print(f"需要保存触发信号数量: {len(triggers)}")
            try:
                self._save_trigger_timestamps(triggers)
            except Exception as e:
                print(f"触发信号处理失败: {e}")
        else:
            print("未检测到触发信号")
            
        return triggers

    def _save_trigger_timestamps(self, triggers):
        """保存触发时间戳
        Args:
            triggers: 触发信号数据
        """
        trigger_polar, trigger_time, _ = zip(*triggers)
        trigger_time = np.array(trigger_time)
        
        timestamp_file = os.path.join(self.path, 'event', 'TimeStamps.txt')
        np.savetxt(timestamp_file, trigger_time, fmt='%d')
        print(f"时间戳已保存至: {timestamp_file}")

    def config_prophesee(self):
        """配置Prophesee相机参数
        Returns:
            bool: 配置是否成功
        """
        ensure_dir(os.path.join(self.path, 'event'))
        
        # 打开相机
        self.device = initiate_device(path='',do_time_shifting=False)
        if not self.device:
            print("未检测到事件相机")
            return False

        # 配置触发
        triggerin = self.device.get_i_trigger_in()
        triggerin.enable(I_TriggerIn.Channel(0))
      
        # 配置事件流
        self.ieventstream = self.device.get_i_events_stream()
        
        # 配置ROI
        if PROPHESEE_Digital_Crop:
            self._config_roi()

        self.device.get_i_ll_biases().set('bias_diff_off', 50)
        self.device.get_i_ll_biases().set('bias_diff_on', 50)
        
        # # # 假设 device 是已初始化的设备对象
        # if PROPHESEE_CUT_TRAIL:
        #     event_trail_filter = self.device.get_i_event_trail_filter_module()
        #     # 设置过滤类型
        #     if event_trail_filter:
        #         available_types = event_trail_filter.get_available_types()
        #         print("Available filter types:", available_types)
        #         # 设置过滤类型为 STC_CUT_TRAIL
        #         event_trail_filter.set_type(I_EventTrailFilterModule.Type.STC_CUT_TRAIL)
        #         # 设置阈值
        #         event_trail_filter.set_threshold(PROPHESEE_FILTER_THS)  #  PROPHESEE_FILTER_THS  = 10000
        #         # 启用过滤器
        #         event_trail_filter.enable(True)
        #         print("Event trail filter enabled.")
        
        return True

    def _config_roi(self):
        """配置ROI区域"""
        Digital_Crop = self.device.get_i_digital_crop()
        Digital_Crop.set_window_region((PROPHESEE_ROI_X0, PROPHESEE_ROI_Y0, 
                                      PROPHESEE_ROI_X1, PROPHESEE_ROI_Y1), False)
        Digital_Crop.enable(True)

    def start_recording(self):
        """开始记录事件流"""
        if not self.ieventstream:
            print("事件流未初始化")
            return 1

        if self.outputpath:
            self.ieventstream.log_raw_data(self.outputpath)
        mv_iterator = EventsIterator.from_device(device=self.device,delta_t=7e4)
        print("事件流记录开始")

        for _ in mv_iterator:
            if ACQUISITION_FLAG.value == 1 or not RUNNING.value:
                break
        self.stop_recording()
        return 0

    def stop_recording(self):
        """停止记录事件流"""
        if self.ieventstream:
            self.ieventstream.stop_log_raw_data()
            print("事件流记录已停止")

def ensure_dir(path):
    """确保目录存在
    Args:
        path (str): 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")
