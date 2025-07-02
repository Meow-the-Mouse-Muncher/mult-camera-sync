import numpy as np
import cv2 as cv
import os
import sys
import time
from pathlib import Path
import struct
import json
import traceback

# 添加必要的路径
sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_sdk_core import OnDemandFrameGenerationAlgorithm

class MultiModalVideoGenerator:
    """三模态数据视频生成器"""
    
    def __init__(self, data_path, output_path=None, fps=20):
        self.data_path = Path(data_path)
        self.output_path = Path(output_path) if output_path else self.data_path / "videos"
        self.fps = fps
        
        # 确保输出目录存在
        self.output_path.mkdir(exist_ok=True)
        
        # 数据路径
        self.flir_path = self.data_path / "flir"
        self.thermal_path = self.data_path / "thermal"
        self.event_path = self.data_path / "event"
        
        # 视频参数
        self.fourcc = cv.VideoWriter_fourcc(*'mp4v')
        
        print(f"数据路径: {self.data_path}")
        print(f"输出路径: {self.output_path}")
    
    def process_flir_data(self):
        """处理FLIR数据并生成MP4"""
        print("正在处理FLIR数据...")
        
        if not self.flir_path.exists():
            print("FLIR路径不存在")
            return False
        
        # 查找FLIR数据文件
        flir_data_file = self.flir_path / "images.raw"
        timestamps_file = self.flir_path / "timestamps.txt"
        
        if not flir_data_file.exists():
            print(f"未找到FLIR数据文件: {flir_data_file}")
            return False
        
        print(f"使用数据文件: {flir_data_file}")
        print(f"文件大小: {flir_data_file.stat().st_size / (1024*1024):.2f} MB")
        
        try:
            # 读取时间戳信息
            timestamps = []
            if timestamps_file.exists():
                with open(timestamps_file, 'r') as f:
                    for line in f:
                        timestamps.append(float(line.strip()))
                print(f"读取到 {len(timestamps)} 个时间戳")
            
            # 读取二进制数据
            with open(flir_data_file, 'rb') as f:
                data = f.read()
            
            print(f"读取数据长度: {len(data)} 字节")
            
            # 解析图像数据
            images = self._parse_flir_raw_data(data, len(timestamps))
            
            if not images:
                print("未能解析FLIR图像数据")
                return False
            
            print(f"成功解析 {len(images)} 张图像")
            
            # 生成视频
            video_path = self.output_path / "flir_video.mp4"
            return self._save_images_to_video(images, video_path, "FLIR")
            
        except Exception as e:
            print(f"处理FLIR数据时出错: {e}")
            traceback.print_exc()
            return False
    
    def _parse_flir_raw_data(self, data, num_images):
        """解析FLIR原始数据"""
        images = []
        
        print(f"开始解析FLIR数据，预期图像数量: {num_images}")
        
        if num_images > 0:
            # 根据数据大小和图像数量推算图像尺寸
            total_pixels = len(data) // num_images
            
            # 检查常见的像素格式
            if total_pixels == 1800 * 1800:
                width, height = 1800, 1800
                pixel_size = 1
                dtype = np.uint8
            elif total_pixels == 1800 * 1800 * 2:
                width, height = 1800, 1800
                pixel_size = 2
                dtype = np.uint16
            else:
                print(f"未知的像素格式，总像素数: {total_pixels}")
                # 尝试自动检测
                if total_pixels > 1800 * 1800:
                    width, height = 1800, 1800
                    pixel_size = 2
                    dtype = np.uint16
                else:
                    width, height = 1800, 1800
                    pixel_size = 1
                    dtype = np.uint8
        else:
            print("没有时间戳信息，使用默认参数")
            width, height = 1800, 1800
            pixel_size = 1
            dtype = np.uint8
            num_images = len(data) // (width * height * pixel_size)
        
        image_size = width * height * pixel_size
        print(f"图像参数 - 尺寸: {width}x{height}, 像素大小: {pixel_size}字节, 图像数量: {num_images}")
        
        try:
            for i in range(num_images):
                start_idx = i * image_size
                end_idx = start_idx + image_size
                
                if end_idx > len(data):
                    break
                
                # 读取原始数据
                image_data = data[start_idx:end_idx]
                raw_image = np.frombuffer(image_data, dtype=dtype)
                raw_image = raw_image.reshape((height, width))
                
                # 转换为RGB（Bayer格式）
                rgb_image = self._convert_bayer_to_rgb(raw_image, dtype)
                
                if rgb_image is not None:
                    images.append(rgb_image)
                
                if (i + 1) % 50 == 0:
                    print(f"已解析 {i+1}/{num_images} 张FLIR图像")
        
        except Exception as e:
            print(f"解析FLIR数据时出错: {e}")
            traceback.print_exc()
            
        print(f"最终成功解析 {len(images)} 张图像")
        return images
    
    def _convert_bayer_to_rgb(self, raw_image, dtype):
        """将Bayer格式转换为RGB"""
        try:
            # 转换为8位
            if dtype == np.uint16:
                min_val = np.min(raw_image)
                max_val = np.max(raw_image)
                if max_val > min_val:
                    bayer_8bit = ((raw_image.astype(np.float32) - min_val) / (max_val - min_val) * 255).astype(np.uint8)
                else:
                    bayer_8bit = np.zeros_like(raw_image, dtype=np.uint8)
            else:
                bayer_8bit = raw_image.astype(np.uint8)
            
            # Bayer转RGB
            rgb_image = cv.cvtColor(bayer_8bit, cv.COLOR_BayerRG2RGB)
            return rgb_image
                    
        except Exception as e:
            print(f"Bayer转RGB失败: {e}")
            # 如果转换失败，使用灰度转RGB
            if len(raw_image.shape) == 2:
                gray_8bit = (raw_image.astype(np.float32) / raw_image.max() * 255).astype(np.uint8)
                return cv.cvtColor(gray_8bit, cv.COLOR_GRAY2RGB)
            return None
    
    def process_thermal_data(self):
        """处理热像仪数据并生成MP4"""
        print("正在处理热像仪数据...")
        
        jpg_files = sorted(list(self.thermal_path.glob("*.jpg")))
        
        if not jpg_files:
            print("未找到热像仪图像文件")
            return False
        
        print(f"找到 {len(jpg_files)} 张热像仪图像")
        
        try:
            images = []
            for i, jpg_file in enumerate(jpg_files):
                img = cv.imread(str(jpg_file), cv.IMREAD_COLOR)
                if img is not None:
                    images.append(img)
                
                if i % 50 == 0:
                    print(f"已加载 {i+1}/{len(jpg_files)} 张热像仪图像")
            
            if images:
                video_path = self.output_path / "thermal_video.mp4"
                return self._save_images_to_video(images, video_path, "Thermal")
            else:
                print("未能加载任何热像仪图像")
                return False
                
        except Exception as e:
            print(f"处理热像仪数据时出错: {e}")
            return False
    
    def process_event_data(self):
        """处理事件相机数据并生成MP4"""
        print("正在处理事件相机数据...")
        
        raw_file = self.event_path / "event.raw"
        
        if not raw_file.exists():
            print(f"未找到事件文件: {raw_file}")
            return False
        
        try:
            # 读取触发器事件
            triggers = self._read_event_triggers(raw_file)
            
            # 生成带极性颜色的事件帧
            frames = self._generate_event_frames_with_polarity(raw_file, triggers)
            
            if frames:
                video_path = self.output_path / "event_video.mp4"
                return self._save_images_to_video(frames, video_path, "Event")
            else:
                print("未能生成事件帧")
                return False
                
        except Exception as e:
            print(f"处理事件数据时出错: {e}")
            traceback.print_exc()
            return False
    
    def _read_event_triggers(self, raw_file):
        """读取事件相机触发器"""
        triggers = None
        try:
            with RawReader(str(raw_file), do_time_shifting=False) as ev_data:
                while not ev_data.is_done():
                    ev_data.load_n_events(1000000)
                triggers = ev_data.get_ext_trigger_events()
                if triggers is not None and len(triggers) > 0:
                    triggers = triggers[triggers['p'] == 0].copy()
                    print(f"找到 {len(triggers)} 个触发器事件")
                else:
                    print("未找到触发器事件，将使用固定时间间隔")
        except Exception as e:
            print(f"读取触发器失败: {e}")
        
        return triggers
    
    def _generate_event_frames_with_polarity(self, raw_file, triggers):
        """生成带极性颜色的事件帧"""
        frames = []
        height, width = 600, 600
        
        try:
            print("读取事件数据...")
            # 读取所有事件数据
            all_events = []
            mv_iterator = EventsIterator(input_path=str(raw_file), delta_t=1e6)
            
            for evs in mv_iterator:
                if evs.size > 0:
                    # 坐标平移
                    evs['x'] = evs['x'] - 340
                    evs['y'] = evs['y'] - 60
                    
                    # 确保坐标在有效范围内
                    valid_mask = (evs['x'] >= 0) & (evs['x'] < width) & (evs['y'] >= 0) & (evs['y'] < height)
                    evs = evs[valid_mask]
                    
                    if evs.size > 0:
                        all_events.append(evs)
            
            if not all_events:
                print("未找到有效的事件数据")
                return []
            
            # 合并所有事件
            combined_events = np.concatenate(all_events)
            print(f"总共 {len(combined_events)} 个事件")
            
            # 按时间排序
            sorted_indices = np.argsort(combined_events['t'])
            combined_events = combined_events[sorted_indices]
            
            print("生成彩色事件帧...")
            
            if triggers is not None and len(triggers) > 0:
                # 使用触发器时间戳生成帧
                for i, trigger in enumerate(triggers):
                    try:
                        timestamp = int(trigger['t'])
                        frame = self._create_polarity_frame(combined_events, timestamp, width, height)
                        
                        if frame is not None:
                            frames.append(frame)
                        
                        if i % 10 == 0:
                            print(f"已生成 {i+1}/{len(triggers)} 帧事件图像")
                            
                    except Exception as e:
                        print(f"生成第 {i} 帧时出错: {e}")
                        continue
            else:
                # 使用固定时间间隔生成帧
                min_time = combined_events['t'].min()
                max_time = combined_events['t'].max()
                
                duration_us = max_time - min_time
                frame_interval_us = int(1e6 / self.fps)
                num_frames = int(duration_us / frame_interval_us)
                
                print(f"生成 {num_frames} 帧，帧率: {self.fps}fps")
                
                for i in range(num_frames):
                    try:
                        timestamp = int(min_time + i * frame_interval_us)
                        frame = self._create_polarity_frame(combined_events, timestamp, width, height)
                        
                        if frame is not None:
                            frames.append(frame)
                        
                        if i % 30 == 0:
                            print(f"已生成 {i+1}/{num_frames} 帧事件图像")
                            
                    except Exception as e:
                        print(f"生成第 {i} 帧时出错: {e}")
                        continue
                        
        except Exception as e:
            print(f"生成事件帧时出错: {e}")
            traceback.print_exc()
            
        print(f"最终生成 {len(frames)} 帧事件图像")
        return frames
    
    def _create_polarity_frame(self, events, timestamp, width, height, accumulation_time_us=20000):
        """创建带极性颜色的事件帧"""
        try:
            # 创建BGR图像
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # 选择时间窗口内的事件
            time_window_start = timestamp - accumulation_time_us // 2
            time_window_end = timestamp + accumulation_time_us // 2
            
            # 找到时间窗口内的事件
            time_mask = (events['t'] >= time_window_start) & (events['t'] <= time_window_end)
            window_events = events[time_mask]
            
            if len(window_events) == 0:
                return frame
            
            # 根据极性设置颜色
            positive_events = window_events[window_events['p'] == 1]  # 正极性事件
            negative_events = window_events[window_events['p'] == 0]  # 负极性事件
            
            # 正极性事件用红色 (BGR: 0, 0, 255)
            if len(positive_events) > 0:
                pos_x = positive_events['x'].astype(int)
                pos_y = positive_events['y'].astype(int)
                valid_pos = (pos_x >= 0) & (pos_x < width) & (pos_y >= 0) & (pos_y < height)
                pos_x = pos_x[valid_pos]
                pos_y = pos_y[valid_pos]
                frame[pos_y, pos_x, 2] = 255  # 红色通道
            
            # 负极性事件用蓝色 (BGR: 255, 0, 0)
            if len(negative_events) > 0:
                neg_x = negative_events['x'].astype(int)
                neg_y = negative_events['y'].astype(int)
                valid_neg = (neg_x >= 0) & (neg_x < width) & (neg_y >= 0) & (neg_y < height)
                neg_x = neg_x[valid_neg]
                neg_y = neg_y[valid_neg]
                frame[neg_y, neg_x, 0] = 255  # 蓝色通道
            
            return frame
            
        except Exception as e:
            print(f"创建极性帧失败: {e}")
            return None
    
    def _save_images_to_video(self, images, video_path, data_type):
        """将图像序列保存为MP4视频"""
        if not images:
            print(f"没有{data_type}图像需要保存")
            return False
        
        print(f"正在保存{data_type}视频: {video_path}")
        
        try:
            # 获取第一张图像的尺寸
            first_image = images[0]
            height, width = first_image.shape[:2]
            
            print(f"视频尺寸: {width}x{height}, 帧数: {len(images)}")
            
            # 创建视频写入器 - 都使用彩色格式
            video_writer = cv.VideoWriter(
                str(video_path),
                self.fourcc,
                self.fps,
                (width, height),
                isColor=True
            )
            
            if not video_writer.isOpened():
                print(f"无法创建视频文件: {video_path}")
                return False
            
            # 写入图像帧
            for i, image in enumerate(images):
                video_writer.write(image)
                
                if i % 50 == 0:
                    print(f"已写入 {i+1}/{len(images)} 帧")
            
            video_writer.release()
            
            # 检查文件大小
            if video_path.exists():
                file_size = video_path.stat().st_size / (1024*1024)
                print(f"{data_type}视频保存成功: {video_path}")
                print(f"文件大小: {file_size:.2f} MB")
                return True
            else:
                print(f"视频文件未创建")
                return False
            
        except Exception as e:
            print(f"保存{data_type}视频时出错: {e}")
            traceback.print_exc()
            return False
    
    def process_all(self):
        """处理所有模态数据"""
        print("开始处理所有模态数据...")
        
        results = {}
        
        # 处理FLIR数据
        if self.flir_path.exists():
            results['flir'] = self.process_flir_data()
        else:
            print("FLIR数据目录不存在")
            results['flir'] = False
        
        # 处理热像仪数据
        if self.thermal_path.exists():
            results['thermal'] = self.process_thermal_data()
        else:
            print("热像仪数据目录不存在")
            results['thermal'] = False
        
        # 处理事件相机数据  
        if self.event_path.exists():
            results['event'] = self.process_event_data()
        else:
            print("事件相机数据目录不存在")
            results['event'] = False
        
        # 打印结果
        print("\n=== 处理结果 ===")
        for modality, success in results.items():
            status = "成功" if success else "失败"
            print(f"{modality.upper()}: {status}")
        
        return results

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="三模态数据MP4视频生成器")
    parser.add_argument("data_path", help="数据目录路径")
    parser.add_argument("--output", "-o", help="输出视频目录路径")
    parser.add_argument("--fps", type=int, default=20, help="视频帧率 (默认: 20)")
    parser.add_argument("--modality", choices=['flir', 'thermal', 'event', 'all'], 
                       default='all', help="处理的模态类型 (默认: all)")
    
    args = parser.parse_args()
    
    # 检查数据路径是否存在
    if not os.path.exists(args.data_path):
        print(f"错误: 数据路径不存在 {args.data_path}")
        return False
    
    # 创建视频生成器
    generator = MultiModalVideoGenerator(
        data_path=args.data_path,
        output_path=args.output,
        fps=args.fps
    )
    
    try:
        if args.modality == 'all':
            results = generator.process_all()
            return any(results.values())
        elif args.modality == 'flir':
            return generator.process_flir_data()
        elif args.modality == 'thermal':
            return generator.process_thermal_data()
        elif args.modality == 'event':
            return generator.process_event_data()
        else:
            print(f"未知的模态类型: {args.modality}")
            return False
            
    except KeyboardInterrupt:
        print("\n用户中断处理")
        return False
    except Exception as e:
        print(f"处理过程中出错: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 如果直接运行，使用默认参数
    if len(sys.argv) == 1:
        # 默认测试路径
        test_data_path = "./data/2025_06_20_11_24_24"
        print(f"使用默认测试路径: {test_data_path}")
        
        if os.path.exists(test_data_path):
            generator = MultiModalVideoGenerator(test_data_path, fps=20)
            generator.process_all()
        else:
            print("请提供数据路径作为参数")
            print("用法: python save_mp4.py <数据路径> [选项]")
            print("例如: python save_mp4.py ./data/2025_06_20_11_24_24")
    else:
        success = main()
        sys.exit(0 if success else 1)