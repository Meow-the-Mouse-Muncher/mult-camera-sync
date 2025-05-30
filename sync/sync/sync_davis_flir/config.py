from multiprocessing import Value
import os
import time
# FLIR相机配置参数
FLIR_FRAMERATE = 70  # fps
FLIR_EXPOSURE_TIME = 500  # us
FLIR_BALANCE_WHITE = 1.6
FLIR_AUTO_EXPOSURE = False  # 自动曝光设置
FLIR_EX_TRIGGER = False  # 触发方式设置  

# FLIR相机分辨率和裁剪设置
FLIR_ORIGIN_WIDTH = 2048   # 原始宽度
FLIR_ORIGIN_HEIGHT = 1536  # 原始高度
FLIR_WIDTH = 2048         
FLIR_HEIGHT = 1536 
# 计算居中偏移量
FLIR_OFFSET_X = (FLIR_ORIGIN_WIDTH - FLIR_WIDTH) // 2   # 水平偏移量
FLIR_OFFSET_Y = (FLIR_ORIGIN_HEIGHT - FLIR_HEIGHT) // 2 # 垂直偏移量


# 触发配置
NUM_IMAGES = 50

# 保存路径配置
BASE_DIR = './data'  # 基础保存目录

