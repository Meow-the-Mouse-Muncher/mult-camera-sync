from multiprocessing import Value

# FLIR相机配置参数
FLIR_FRAMERATE = 20  # fps
FLIR_EXPOSURE_TIME = 50000  # us
FLIR_BALANCE_WHITE = 1.6
FLIR_AUTO_EXPOSURE = False  # 自动曝光设置
FLIR_EX_TRIGGER = False  # 触发方式设置

# FLIR相机分辨率和裁剪设置
FLIR_ORIGIN_WIDTH = 2448   # 原始宽度
FLIR_ORIGIN_HEIGHT = 2048  # 原始高度
FLIR_WIDTH = 1800         # 裁剪后宽度
FLIR_HEIGHT = 1800        # 裁剪后高度
# 计算居中偏移量
FLIR_OFFSET_X = (FLIR_ORIGIN_WIDTH - FLIR_WIDTH) // 2   # 水平偏移量
FLIR_OFFSET_Y = (FLIR_ORIGIN_HEIGHT - FLIR_HEIGHT) // 2 # 垂直偏移量
FLIR_ThroughputLimit = 5e8  # 限制相机吞吐量
# FLIR_ThroughputLimit = 430 000 000 500 000 000.  # 限制相机吞吐量

# 红外相机配置参数
THERMAL_CAMERA_IP = "192.168.1.11"
THERMAL_CAMERA_PORT = None  # 设置为 None 时会自动计算
THERMAL_WIDTH = 640
THERMAL_HEIGHT = 512
THERMAL_FPS = FLIR_FRAMERATE  # 与FLIR相机保持相同帧率
THERMAL_TEMP_SEGMENT = 0  # 温度段 (0:常温段, 1:中温段, 2:高温段)

# Prophesee事件相机配置
PROPHESEE_FILTER_THS = 100000  # Length of the time window for filtering (in us)
PROPHESEE_CUT_TRAIL = True  # If true, after an event goes through, it removes all events until change of polarity
PROPHESEE_ROI_X0 = 340
PROPHESEE_ROI_Y0 = 60
PROPHESEE_ROI_X1 = 939
PROPHESEE_ROI_Y1 = 659

# 触发配置
NUM_IMAGES = 100 + 1  # number of images to save (+1 because prophesee first trigger is incomplete)
# 串口配置
SERIAL_PORT = '/dev/ttyTHS1'
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1

# 保存路径配置
BASE_DIR = './data'  # 基础保存目录

# 全局状态控制
ACQUISITION_FLAG = Value('i', 0)  # 'i' 表示整型
RUNNING = Value('i', 1)  # 'i' 表示整型
