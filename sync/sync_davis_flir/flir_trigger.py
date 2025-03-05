from config import * 
from flir_lib import FlirCamera
import time
import os

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
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S_flir", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    # 创建预览图像目录
    ensure_dir(os.path.join(save_path, 'images'))
    print(f"数据将保存至: {save_path}")
    return save_path

save_path = create_save_directories(BASE_DIR)

try:
    # 初始化FLIR相机
    flir = FlirCamera()
    if not flir.initialize():
        print("FLIR相机初始化失败")
except:
    print("FLIR相机初始化失败")

for i, cam in enumerate(flir.cam_list):
    print(f'正在配置FLIR相机 {i}...')
    try:
        # 初始化相机
        cam.Init()
        nodemap = cam.GetNodeMap()

        # 配置相机
        if not flir.config_camera(nodemap):
            print("FLIR相机配置失败")
        print("FLIR相机配置成功")  
        # 开始采集
        cam.BeginAcquisition()
        flir.acquire_images(cam, nodemap, save_path)
        # 确保相机停止采集
        if cam.IsStreaming():
            cam.EndAcquisition()
        cam.DeInit()
        del cam
        flir.cleanup()

    except Exception as ex:
        print(f'相机操作错误: {ex}')
