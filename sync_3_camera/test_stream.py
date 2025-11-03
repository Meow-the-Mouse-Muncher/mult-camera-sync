import numpy as np
import cv2 as cv
import time
import sys
import os
from lib import streamPiper
sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device
from metavision_hal import I_EventTrailFilterModule
from metavision_sdk_core import OnDemandFrameGenerationAlgorithm

def test_stream_piper_with_raw_file(raw_file_path, use_triggers=True, fps=30):
    """
    使用OnDemandFrameGenerationAlgorithm处理event.raw文件并推流
    
    参数:
    raw_file_path: event.raw文件路径
    use_triggers: 是否使用触发器事件作为时间戳
    fps: 如果不使用触发器，设置推流帧率
    """
    
    # 初始化 streamPiper 实例
    stream_width = 600
    stream_height = 600
    stream_piper = streamPiper.streamPiper(stream_width, stream_height)
    
    try:
        print(f"开始处理文件: {raw_file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(raw_file_path):
            print(f"警告: 事件文件不存在 {raw_file_path}")
            return
        
        # 读取触发器事件（如果使用）
        triggers = None
        if use_triggers:
            try:
                with RawReader(raw_file_path, do_time_shifting=False) as ev_data:
                    while not ev_data.is_done():
                        ev_data.load_n_events(1000000)
                    triggers = ev_data.get_ext_trigger_events()
                    triggers = triggers[triggers['p'] == 0].copy()
                    triggers['t'] = triggers['t']
                print(f"找到 {len(triggers)} 个触发器事件")
            except Exception as e:
                print(f"读取触发器失败，将使用固定帧率模式: {e}")
                use_triggers = False
        
        # 初始化事件帧生成器
        height, width = stream_height, stream_width
        mv_iterator = EventsIterator(input_path=raw_file_path, delta_t=1e6)
        on_demand_gen = OnDemandFrameGenerationAlgorithm(height, width, accumulation_time_us=10000)
        
        print("开始处理事件数据...")
        # 处理所有事件数据
        for evs in mv_iterator:
            if evs.size > 0:  # 确保事件数组不为空
                # 坐标平移
                evs['x'] = evs['x'] - 340
                evs['y'] = evs['y'] - 60
                
                # 确保坐标在有效范围内
                valid_mask = (evs['x'] >= 0) & (evs['x'] < width) & (evs['y'] >= 0) & (evs['y'] < height)
                evs = evs[valid_mask]
                
                if evs.size > 0:
                    on_demand_gen.process_events(evs)
        
        print("事件数据处理完成，开始生成帧并推流...")
        
        if use_triggers and triggers is not None and len(triggers) > 0:
            # 使用触发器时间戳生成帧
            frame_count = 0
            for i, trigger in enumerate(triggers):
                try:
                    # 创建帧缓冲区
                    frame = np.zeros((height, width, 3), np.uint8)
                    
                    # 在指定时间戳生成事件帧
                    timestamp = int(trigger['t'])
                    on_demand_gen.generate(timestamp, frame)
                    
                    # 推送到streamPiper
                    stream_piper.push(frame)
                    frame_count += 1
                    
                    if frame_count % 10 == 0:
                        print(f"已推送 {frame_count}/{len(triggers)} 帧")
                    
                    # 控制推送速度
                    time.sleep(1.0 / fps)
                    
                except Exception as e:
                    print(f"生成第 {i} 帧时出错: {e}")
                    continue
        else:
            # 固定帧率模式：基于事件时间范围生成均匀分布的时间戳
            print("使用固定帧率模式")
            
            # 重新读取事件获取时间范围
            mv_iterator_time = EventsIterator(input_path=raw_file_path, delta_t=1e6)
            min_time, max_time = None, None
            
            for evs in mv_iterator_time:
                if evs.size > 0:
                    if min_time is None:
                        min_time = evs['t'].min()
                    max_time = evs['t'].max()
            
            if min_time is not None and max_time is not None:
                duration_us = max_time - min_time
                frame_interval_us = int(1e6 / fps)  # 帧间隔（微秒）
                num_frames = int(duration_us / frame_interval_us)
                
                print(f"时间范围: {min_time} - {max_time} ({duration_us/1e6:.2f}秒)")
                print(f"将生成 {num_frames} 帧，帧率: {fps}fps")
                
                frame_count = 0
                for i in range(num_frames):
                    try:
                        # 创建帧缓冲区
                        frame = np.zeros((height, width, 3), np.uint8)
                        
                        # 计算当前时间戳
                        timestamp = int(min_time + i * frame_interval_us)
                        on_demand_gen.generate(timestamp, frame)
                        
                        # 推送到streamPiper
                        stream_piper.push(frame)
                        frame_count += 1
                        
                        if frame_count % 30 == 0:
                            print(f"已推送 {frame_count}/{num_frames} 帧")
                        
                        # 控制推送速度
                        time.sleep(1.0 / fps)
                        
                    except Exception as e:
                        print(f"生成第 {i} 帧时出错: {e}")
                        continue
            else:
                print("无法获取事件时间范围")
                
        print("推流完成!")
        
    except KeyboardInterrupt:
        print("推流已停止。")
    except Exception as e:
        print(f"处理event.raw文件时出错: {e}")
        import traceback
        traceback.print_exc()

def test_stream_piper():
    """原始测试函数 - 使用随机数据"""
    # 初始化 streamPiper 实例
    stream_width = 600
    stream_height = 600
    stream_piper = streamPiper.streamPiper(stream_width, stream_height)

    try:
        print("开始持续推送测试数据到 streamPiper...")
        while True:
            # 创建测试图像数据
            test_image = np.random.randint(0, 256, (stream_height, stream_width), dtype=np.uint8)
            test_image_rgb = cv.cvtColor(test_image, cv.COLOR_GRAY2RGB)  # 转换为 RGB 格式

            # 推送数据到 streamPiper
            stream_piper.push(test_image_rgb)
            print("测试数据推送成功！")
            
            # 控制推送频率
            time.sleep(0.1)  # 每 100 毫秒推送一次
    except KeyboardInterrupt:
        print("推送测试数据已停止。")
    except Exception as e:
        print(f"推送数据到 streamPiper 时出错: {e}")

if __name__ == "__main__":
    # 指定 event.raw 文件路径
    raw_file_path = "./data/2025_06_19_21_53_34/event/event.raw"  # 请修改为实际的文件路径
    
    # 配置参数
    use_triggers = False  # 是否使用触发器事件
    fps = 20  # 如果不使用触发器，设置推流帧率
    
    # 检查文件是否存在
    if os.path.exists(raw_file_path):
        test_stream_piper_with_raw_file(raw_file_path, use_triggers, fps)
    else:
        print(f"文件不存在: {raw_file_path}")
        print("使用随机数据进行测试...")
        test_stream_piper()