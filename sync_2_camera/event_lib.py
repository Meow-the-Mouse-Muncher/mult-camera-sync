import sys
import os
import datetime
import numpy as np
from config import *

sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device
from metavision_hal import I_EventTrailFilterModule
from metavision_sdk_core import OnDemandFrameGenerationAlgorithm
os.environ['LD_LIBRARY_PATH'] = '/home/nvidia/code/mult-camera-sync/sync/sync_3_camera/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
# from lib import streamPiper

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
        self.time_path = os.path.join(path, 'event', 'star_end_time.txt')
        self.timestamps = np.zeros((2,), dtype=np.float64)
        self.ieventstream = None
        self.device = None

    def prophesee_tirgger_found(self, polarity: int = 0, do_time_shifting=False):
        """
        查找触发信号并保存时间戳（使用EventsIterator进行真正的分块读取）。
        Args:
            polarity (int): 触发极性，0为正，1为负。
            do_time_shifting (bool): 是否进行时间偏移。
        Returns:
            triggers: 触发信号数据。
        """
        all_triggers = []
        # 定义每次迭代处理的事件数量，这是一个安全的内存占用方式
        iterator_n_events = 200000 

        try:
            print("开始使用EventsIterator分块读取事件文件以查找触发信号...")
            
            # 从.raw文件创建EventsIterator
            mv_iterator = EventsIterator(str(self.outputpath), n_events=iterator_n_events)

            # 迭代处理每个事件块
            for evs in mv_iterator:
                # 在每个事件块(evs)中，筛选出外部触发事件
                # 外部触发事件的 channel ID 通常是 0 或 1，这里我们检查所有非像素事件
                # 触发事件的 'x' 坐标通常是固定的，并且 'y' 坐标代表 channel ID
                # 假设外部触发的 'y' 坐标为 0
                trigger_events_in_chunk = evs[evs['y'] == 0] # 这是一个示例，具体ID可能不同，请根据设备手册确认
                
                if len(trigger_events_in_chunk) > 0:
                    # 将找到的触发事件添加到总列表中
                    # 注意：这里的字段名可能需要根据实际情况调整 ('p', 't')
                    # 从EventsIterator得到的事件通常有 'x', 'y', 'p', 't' 字段
                    for trigger in trigger_events_in_chunk:
                        # 构造与get_ext_trigger_events()返回格式一致的元组
                        # (polarity, timestamp, id) -> id 在这里我们用 'x'
                        all_triggers.append((trigger['p'], trigger['t'], trigger['x']))

            # 如果找到了触发事件，进行后续处理
            if all_triggers:
                # 将列表转换为结构化numpy数组，dtype需要与get_ext_trigger_events()的输出匹配
                # 字段名 'p', 't', 'id' 是标准格式
                triggers = np.array(all_triggers, dtype=[('p', 'i4'), ('t', 'i8'), ('id', 'i4')])
                
                print(f"总共检测到 {len(triggers)} 个触发信号")
                self._save_trigger_timestamps(triggers)

                if polarity in (0, 1):
                    triggers = triggers[triggers['p'] == polarity].copy()
                print(f"根据极性 {polarity} 筛选后，需要处理 {len(triggers)} 个触发信号")
            else:
                print("未检测到任何触发信号")
                triggers = np.array([])
            
            return triggers

        except Exception as e:
            print(f"使用EventsIterator处理事件文件时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

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

        # self.device.get_i_ll_biases().set('bias_diff_off',50)
        # self.device.get_i_ll_biases().set('bias_diff_on', 50)
        # 配置ERC
        erc_module = self.device.get_i_erc_module()
        if erc_module:
            # 设置CD事件率
            erc_module.set_cd_event_rate(EVENT_RATE_LIMIT)
            # 启用ERC
            erc_module.enable(True)
            # 读取实际设置的事件率
            current_rate = erc_module.get_cd_event_rate()
            print("Event Rate Control enabled:")
            print(f"- CD event rate: {current_rate/1000000:.1f}MEv/s")

        # self.device.get_i_ll_biases().set('bias_hpf', 60)
        # self.device.get_i_ll_biases().set('bias_fo', 40)
        
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
            star_time = datetime.datetime.now().timestamp()
            self.timestamps[0] = star_time

        mv_iterator = EventsIterator.from_device(device=self.device,delta_t=7e4,
                                                 )
        # print("事件流记录开始")
        # on_demand_gen = OnDemandFrameGenerationAlgorithm(600, 600, accumulation_time_us=40000)
        # frame_period_us = int(1e6/12)  # 12FPS
        # next_processing_ts = frame_period_us
        # frame = np.zeros((600, 600, 3), np.uint8)
        # stream_push = streamPiper.streamPiper(600,600)
        for evs in mv_iterator:
            # evs['x'] = evs['x'] - 340
            # evs['y'] = evs['y'] - 60
            # on_demand_gen.process_events(evs)  # Feed events to the frame generator
            # if len(evs["t"]) == 0:
            #     continue  # 跳过无事件的帧
            # ts = evs["t"][-1] # Trigger new frame generations as long as the last event is high enough
            # while(ts > next_processing_ts):
            #     on_demand_gen.generate(next_processing_ts, frame)
            #     stream_push.push(frame)
            #     next_processing_ts += frame_period_us
            if ACQUISITION_FLAG.value == 1 or not RUNNING.value:
                break
        self.stop_recording()
        return 0

    def stop_recording(self):
        """停止记录事件流"""
        if self.ieventstream:
            self.ieventstream.stop_log_raw_data()
            self.timestamps[1] = datetime.datetime.now().timestamp()
            np.savetxt(self.time_path, self.timestamps)
            print("事件流记录已停止")

def ensure_dir(path):
    """确保目录存在
    Args:
        path (str): 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")
