import numpy as np
import cv2 as cv
import os
def apply_white_balance(image, percentile=99):
    """
    对图像进行白平衡处理
    :param image: BGR格式的图像
    :param percentile: 用于计算白点的百分位数
    :return: 白平衡后的图像
    """
    result = cv.cvtColor(image, cv.COLOR_BGR2LAB)
    avg_a = np.average(result[:, :, 1])
    avg_b = np.average(result[:, :, 2])
    
    result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * (result[:, :, 0] / 255.0) * 1.1)
    result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * (result[:, :, 0] / 255.0) * 1.1)
    
    return cv.cvtColor(result, cv.COLOR_LAB2BGR)

def read_raw_images(raw_file_path, output_dir):
    """
    从raw文件读取图像并进行处理
    :param raw_file_path: raw文件路径
    :param output_dir: 输出目录
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    with open(raw_file_path, 'rb') as f:
        # 读取头信息
        header = np.frombuffer(f.read(5 * 4), dtype=np.int32)
        num_images, offset_x, offset_y, width, height = header
        
        # 逐帧读取图像
        for idx in range(num_images):
            # 读取一帧图像数据
            img_data = np.frombuffer(f.read(width * height), dtype=np.uint8)
            img_data = img_data.reshape((height, width))
            
            # 确定Bayer模式并转换为RGB
            pattern_key = (offset_x % 2, offset_y % 2)
            bayer_patterns = {
                (0, 0): cv.COLOR_BayerRG2BGR,
                (1, 0): cv.COLOR_BayerGR2BGR,
                (0, 1): cv.COLOR_BayerGB2BGR,
                (1, 1): cv.COLOR_BayerBG2BGR
            }
            
            bgr_image = cv.cvtColor(img_data, bayer_patterns[pattern_key])
            
            # 应用白平衡
            balanced_image = apply_white_balance(bgr_image)
            
            # 保存图像
            output_path = os.path.join(output_dir, f'frame_{idx:04d}.png')
            cv.imwrite(output_path, balanced_image)
            
            if idx % 10 == 0:
                print(f'Processed frame {idx}/{num_images}')

if __name__ == '__main__':
    raw_file_path = 'images.raw'  # raw文件路径
    output_dir = 'extracted_images'  # 输出目录
    #保证路径都是存在的
    if not os.path.exists(raw_file_path):
        print(f'Raw file not found: {raw_file_path}')
        exit(1)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    read_raw_images(raw_file_path, output_dir)