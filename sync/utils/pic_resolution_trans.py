from PIL import Image
import os

# 设置文件夹路径
folder1 = 'path_to_folder1'  # 替换为你的文件夹1的路径
folder2 = 'path_to_folder2'  # 替换为你的文件夹2的路径

# 获取文件夹2中第一个图像的分辨率
first_image_path = os.path.join(folder2, os.listdir(folder2)[0])
first_image = Image.open(first_image_path)
target_resolution = first_image.size

# 遍历文件夹1中的所有图像
for image_name in os.listdir(folder1):
    image_path = os.path.join(folder1, image_name)
    
    # 确保是文件而不是文件夹
    if os.path.isfile(image_path):
        # 打开图像
        image = Image.open(image_path)
        
        # 调整图像分辨率
        resized_image = image.resize(target_resolution, Image.ANTIALIAS)
        
        # 保存调整后的图像
        resized_image.save(image_path)

print("所有图像的分辨率已调整完毕。")