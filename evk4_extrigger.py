# import PySpin
import sys
import time
import os
import Jetson.GPIO as GPIO
import sys
import tkinter as tk
import tkinter.font as tkf
from threading import Thread
import numpy as np
import queue
import cv2 as cv
sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
#逐行输出sys.path内容
# print('\n'.join(sys.path))

from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device



# 全局变量设置
NUM_IMAGES = 20+1  # number of images to save
#prophesee first trigger is incompelete, so we save one more image
# evk4 触发反向了
## flir camera set
FRAMERATE = int(15) # fps
EXPOSURE_TIME = 50000 # us
Auto_Exposure = False   #自动曝光设置
EX_Trigger = True      #触发方式设置
Save_mode = True  ## 单张存false npy存 true
expose_time = EXPOSURE_TIME #us
frequency =int(FRAMERATE) # 设置频率
duty_cycle = 50 # 设置占空比为50
trigger_io = 18

# prophesee camera set
stc_filter_ths = 10000  # Length of the time window for filtering (in us)
stc_cut_trail = True  # If true, after an event goes through, it removes all events until change of polarity
nameoutglob = 1
acquisition_flag = 0   # 保证 evk4 的采集
# 硬件裁剪
roi_x0 = int(340)
roi_y0 = int(60)
roi_x1 = int(939)
roi_y1 = int(659)
#  flir camera set
OFFSET_X = 224
OFFSET_Y = 524
WIDTH = 2000
HEIGHT = 1000
class AviType:
    """'Enum' to select AVI video type to be created and saved"""
    UNCOMPRESSED = 0
    MJPG = 1
    H264 = 2
chosenAviType = AviType.UNCOMPRESSED  # change me!

GPIO.setmode(GPIO.BOARD)
GPIO.setup(trigger_io, GPIO.OUT, initial=GPIO.LOW)
def trigger_star(out_io,fre,duty_cycle):
    for i in range(NUM_IMAGES):
        try:
            # while (1):
            GPIO.output(out_io, GPIO.HIGH)
            time.sleep(0.3/fre)
            GPIO.output(out_io, GPIO.LOW)
            time.sleep(0.7/fre)
            # print(i)  
        except KeyboardInterrupt:
            # 捕获Ctrl+C信号来终止程序
            print("程序终止")
    print("pulse is over ")
    GPIO.output(out_io, GPIO.LOW)
    global acquisition_flag
    acquisition_flag = 1
    GPIO.cleanup()
    return 0

class event():
    def __init__(self,num,path):
        self.num = num
        self.width = 1280
        self.height = 720
        self.path = path
        self.outputpath = os.path.join(path, 'event', 'event.raw')
        self.ieventstream = None
        self.device = None
    def prophesee_tirgger_found(self,polarity: int = 0,do_time_shifting=True):
        triggers = None
        with RawReader(str(self.outputpath), do_time_shifting=do_time_shifting) as ev_data:
            while not ev_data.is_done():
                a = ev_data.load_n_events(1000000)
            triggers = ev_data.get_ext_trigger_events()
        print(f"total triggers num = {len(triggers)} pos and neg")

        #---------------需要测试触发信号的数量和时间----------------#
        print(f"the first trigger is {triggers['p'][0]} ,and time is {triggers['t'][0]}")
        print(f"the second trigger is {triggers['p'][1]} ,and time is {triggers['t'][1]}")
        print(f"the last trigger is {triggers['p'][-1]} ,and time is {triggers['t'][-1]}")



        # 1 is neg , 0 is pos
        if polarity in (0, 1): 
            triggers = triggers[triggers['p'] == polarity].copy()
        else:
            triggers = triggers.copy()
        try:
            print(f"pos triggers num = {len(triggers)}")
            triggers = triggers[:NUM_IMAGES-1]     
            
            print(f"we need pos triggers num = {len(triggers)}")
            trigger_polar, trigger_time, cam = zip(*triggers)
            trigger_polar = np.array(trigger_polar)
            trigger_time = np.array(trigger_time)
            # wirte time to a txt file
            with open(os.path.join(self.path, 'event', 'TimeStamps.txt'), "w+") as f:
                for i in range(len(trigger_time)):
                    timestamp =trigger_time[i]
                    f.write('{}'.format(int(timestamp)) +'\n')
        except:
            print(f"no trigger signal!")
        return triggers

    def config_prophesee(self):
        """Main function"""
        ensure_dir(os.path.join(self.path, 'event'))
        # Open camera
        self.device = initiate_device(path='')
        if not self.device:
            print("Could not open camera. Make sure you have an event-based device plugged in")
            exit()
            return 1
        # set trigger
        triggerin = self.device.get_i_trigger_in()
        triggerin.enable(I_TriggerIn.Channel(0))
      
        # 访问事件流功能
        self.ieventstream = self.device.get_i_events_stream()
        print(self.ieventstream)
        # 裁剪图像 硬件裁剪
        global roi_x0, roi_y0, roi_x1, roi_y1
        Digital_Crop = self.device.get_i_digital_crop()
        Digital_Crop.set_window_region((roi_x0, roi_y0, roi_x1, roi_y1),False)
        Digital_Crop.enable(True)
        
        
        return True
    def start_recording(self):
        # 开始录制

        if self.ieventstream:
            if (self.outputpath != ""):
                self.ieventstream.log_raw_data(self.outputpath)
        else:
            print("no events stream")

        mv_iterator = EventsIterator.from_device(device=self.device, max_duration=1200000000)
        # 接受事件流
        print("events stream start")
        height, width = mv_iterator.get_size()  # Camera Geometry
        print(f"height = {height}, width = {width}")
        global acquisition_flag
        print("flag is ",acquisition_flag)
        for evs in mv_iterator:
            if acquisition_flag == 1:
                break
        return 0
    def stop_recording(self):
        self.ieventstream.stop_log_raw_data()
        print("event stop recording")
        del self.device

        return 0
    

def ensure_dir(s):
    if not os.path.exists(s):
        os.makedirs(s)







def main():
    """
    Example entry point; please see Enumeration example for more in-depth
    comments on preparing and cleaning up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """

    # Since this application saves images in the current folder
    # we must ensure that we have permission to write to this folder.
    # If we do not have permission, fail right away.
    try:
        test_file = open('test.txt', 'w+')
    except IOError:
        print('Unable to write to current directory. Please check permissions.')
        input('Press Enter to exit...')
        return False

    test_file.close()
    os.remove(test_file.name)

    result = True
    # Retrieve singleton reference to system object




    ## config prophesee camera
    path = os.path.join('./', time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))
    ensure_dir(path) 
    prophesee_cam = event(0,path)
    prophesee_cam.config_prophesee()
   # while(1):
    #	print("set")
    # Run example on each camera
    global acquisition_flag
    acquisition_flag = 0
    # 多线程配置 
    print("线程开始")
    prophesee_thread = Thread(target=prophesee_cam.start_recording,args=()) 
    trigger_thread =Thread(target=trigger_star,args=(trigger_io,frequency,duty_cycle))
    #多线程启动
    prophesee_thread.start()
    trigger_thread.start()
    
    trigger_thread.join()
    prophesee_thread.join()
    try : 
        acquisition_flag = 0 # 结束了采集
        prophesee_cam.stop_recording()
        prophesee_cam.prophesee_tirgger_found()
    except :
        print("save is wrong")


   


    return result


if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)

