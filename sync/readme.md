# 三相机外同步脚本使用说明
## 1. 系统要求

### 支持平台
- Windows (32/64位)
- Linux (x86/arm32/arm64)



## 2. 硬件配置

- FLIR BFLY-PGE-50S5 相机
- EVK4 事件相机
- k46e19 红外相机
- xavier 开发板
- 树莓派4B
- HM30 图传

## 3. 各文件夹说明

### e2calib 
用于将事件相机转为灰度图进行标定，参考[e2calib](https://github.com/uzh-rpg/e2calib "e2calib") 
### gst 
flir相机的图传脚本，在采集脚本运行之前应该关闭此脚本，防止冲突
### nosync
远古时期为了测试开发板xavier的时候写的
### rp4
远古时期使用树莓派4作为主控，发现配置不够，故放弃
### sync
``` 
├─sync
│  ├─.vscode
│  └─sync_3_camera
│      ├─lib
│      └─__pycache__
```
sync_3_camera 文件夹之外的是rgb+evk4的捕获脚本，后更新到sync_3_camera文件夹中，相机配置在config.py中修改，有双/三相机脚本。ps：此版本使用rp4产生触发信号
### test_camera 
相关相机测试
### thermal
红外相机的demo和相关配置软件
### utils
相关的远古文件
### cam_streaming.sh
图传启动脚本

## 4. 使用方式
1. 图传启动

    ```bash
    sudo cam_streaming.sh
    ```
2. 采集脚本启动

    ```bash
    sudo python sync_3_camera.py
    ```

