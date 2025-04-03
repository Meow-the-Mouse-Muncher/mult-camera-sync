import time
import dv_processing as dv
from dv_processing import TriggerType
import os
from config import *

# DAVIS
def ensure_dir(path):
    """确保目录存在
    Args:
        path (str): 目录路径
    """
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")

def create_save_directories(base_path):
    """创建保存目录结构
    Args:
        base_path (str): 基础保存路径
    Returns:
        str: 完整的保存路径
    """
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S_davis", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    ensure_dir(save_path)
    print(f"数据将保存至: {save_path}")
    return save_path

save_path = create_save_directories(BASE_DIR)

print("******************************************************")
print("Recording DAVIS Data!")

# 初始化相机
cameras = dv.io.discoverDevices()
if not cameras:
    raise RuntimeError("没有找到DVS相机")

# 获取并初始化相机
camera = cameras[0]
capture = dv.io.CameraCapture(cameraName=camera)

# 检查数据流是否可用
eventsAvailable = capture.isEventStreamAvailable()
imuAvailable = capture.isImuStreamAvailable()
triggersAvailable = capture.isTriggerStreamAvailable()

if not triggersAvailable:
    raise RuntimeError("触发器数据流不可用")

# 配置触发器
capture.deviceConfigSet(4, 1, True)  # 启用上升沿检测
capture.deviceConfigSet(4, 2, True)  # 启用下降沿检测
capture.deviceConfigSet(4, 0, True)  # 启用检测器

# 初始化时间戳列表
timestamp_falling_edges = []
timestamp_rising_edges = []

try:
    # 配置writer处理所有可用的数据流
    writer = dv.io.MonoCameraWriter(os.path.join(save_path, 'davis.aedat4'), capture)
    print(f"事件流是否可用: {str(writer.isEventStreamConfigured())}")
    print(f"IMU数据流是否可用: {str(writer.isImuStreamConfigured())}")
    print(f"触发器数据流是否可用: {str(writer.isTriggerStreamConfigured())}")
    print("Recording started!")
    
    # 主循环
    while capture.isRunning():
        # 检查是否达到目标图像数
        if len(timestamp_falling_edges) >= NUM_IMAGES:
            break
            
        # 处理事件流数据
        if eventsAvailable:
            events = capture.getNextEventBatch()
            if events is not None:
                writer.writeEvents(events, streamName='events')
        
        # 处理IMU数据
        if imuAvailable:
            imus = capture.getNextImuBatch()
            if imus is not None:
                writer.writeImuPacket(imus, streamName='imu')

        # 处理触发器数据
        if triggersAvailable:
            triggers = capture.getNextTriggerBatch()
            if triggers is not None:
                writer.writeTriggerPacket(triggers, streamName='triggers')
                # 处理触发器数据
                for trigger in triggers:
                    if trigger.type == TriggerType.EXTERNAL_SIGNAL_FALLING_EDGE:
                        timestamp_falling_edges.append(trigger.timestamp)
                    elif trigger.type == TriggerType.EXTERNAL_SIGNAL_RISING_EDGE:
                        timestamp_rising_edges.append(trigger.timestamp)      
except KeyboardInterrupt:
    print("\n程序被用户中断")
except Exception as e:
    print(f"发生错误: {e}")
finally:
    if 'writer' in locals():
        del writer
    if 'capture' in locals():
        del capture
    print("程序结束")

# 输出触发器统计信息
num_falling_edge = len(timestamp_falling_edges)
num_rising_edge = len(timestamp_rising_edges)
print(f"上升沿触发次数: {num_rising_edge}")
print(f"下降沿触发次数: {num_falling_edge}")

# 保存时间戳
with open(os.path.join(save_path, 'timestamp.txt'), 'w') as f:
    for timestamp in timestamp_rising_edges:
        f.write(str(timestamp) + '\n')
