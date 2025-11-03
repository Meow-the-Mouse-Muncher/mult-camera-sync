sudo LD_LIBRARY_PATH=/home/nvidia/code/mult-camera-sync-new/sync/sync_3_camera/lib python sync_3_camera_async.py
sudo LD_LIBRARY_PATH=/home/nvidia/code/mult-camera-sync-new/sync/sync_3_camera/lib python test_stream.py

sudo LD_LIBRARY_PATH=/home/nvidia/code/mult-camera-sync-new/sync/sync_3_camera/lib python sync_3_camera_async_fr.py 


conda activate sync_camera
sudo LD_LIBRARY_PATH=/home/nvidia/code/mult-camera-sync-new/sync/sync_3_camera/lib python sync_3_camera_async_fr.py 

/home/nvidia/code/mult-camera-sync-new/sync/sync_3_camera/sync_3_camera_async_fr.py

# Bias参数配置

## bias_diff
- **默认值**: 0
- **最小值**: -25
- **最大值**: 23

## bias_diff_on
- **默认值**: 0
- **最小值**: -85
- **最大值**: 140

## bias_diff_off
- **默认值**: 0
- **最小值**: -35
- **最大值**: 190

## bias_fo
- **默认值**: 0
- **最小值**: -35
- **最大值**: 55
增加bias_fo以扩大带宽 

## bias_hpf
- **默认值**: 0
- **最小值**: 0
- **最大值**: 120
降低 bias_hpf 以降低传感器的截止频率，使其能够检测到更低频的信号，让传感器对较慢的光线变化更加敏感

## bias_refr
- **默认值**: 0
- **最小值**: -20
- **最大值**: 235


bias_fo 		0 	-35 	55 	
bias_hpf 	