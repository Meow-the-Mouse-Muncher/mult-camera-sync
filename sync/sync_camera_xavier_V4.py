import PySpin
import sys
import serial
import time
import os
import Jetson.GPIO as GPIO
import sys
import tkinter as tk
import tkinter.font as tkf
from threading import Thread
import numpy as np
import queue
import signal
import cv2 as cv
sys.path.append("/home/nvidia/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/nvidia/openeb/build/py3")
#逐行输出sys.path内容
# print('\n'.join(sys.path))

from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device
from metavision_hal import I_EventTrailFilterModule


# 全局变量设置
NUM_IMAGES = 20+1  # number of images to save
#prophesee first trigger is incompelete, so we save one more image
# evk4 触发反向了
## flir camera set
FRAMERATE = int(10) # fps
EXPOSURE_TIME = 50000 # us
BALANCE_WHITE = 1.6
Auto_Exposure = False   #自动曝光设置
EX_Trigger = True      #触发方式设置
expose_time = EXPOSURE_TIME #us
frequency =int(FRAMERATE) # 设置频率
duty_cycle = 50 # 设置占空比为50
trigger_io = 11

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
OFFSET_X = 324
OFFSET_Y = 124
WIDTH = 1800
HEIGHT = 1800


global cam_list, system 
running = True
def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Cleaning up...')
    global running
    running = False
    # 停止所有相机的采集
    for cam in cam_list:
        try:
            cam.EndAcquisition()
            cam.DeInit()
        except:
            pass
    # 清空相机列表
    cam_list.Clear()
    # 释放系统实例
    system.ReleaseInstance()
    sys.exit(0)

# 注册信号处理程序
signal.signal(signal.SIGINT, signal_handler)


## 指令发送函数
ser = serial.Serial('/dev/ttyTHS1', 115200, timeout=1)  # 根据实际情况修改串口名和波特率  
def send_pulse_command(num_pulses, frequency):  
    # 构造指令（这里使用简单的字符串格式，可以根据需要定义更复杂的协议）  
    command = f"PULSE,{num_pulses},{frequency}\n"  
    ser.write(command.encode())  
    print(f"Sent command: {command.strip()}")  



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
        
        # 假设 device 是已初始化的设备对象
        event_trail_filter = self.device.get_i_event_trail_filter_module()
        # 设置过滤类型
        if event_trail_filter:
            available_types = event_trail_filter.get_available_types()
            print("Available filter types:", available_types)
            # 设置过滤类型为 STC_CUT_TRAIL
            event_trail_filter.set_type(I_EventTrailFilterModule.Type.STC_CUT_TRAIL)
            # 设置阈值
            event_trail_filter.set_threshold(100000)  # 设置阈值为100000微秒
            # 启用过滤器
            event_trail_filter.enable(True)
            print("Event trail filter enabled.")
        
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
        global running
        print("flag is ",acquisition_flag)
        for evs in mv_iterator:
            if acquisition_flag == 1 or not running:
                break
            pass

        self.ieventstream.stop_log_raw_data()
        print("event stop recording")
        return 0
    
    def stop_recording(self):
        # 停止录制
        self.ieventstream.stop_log_raw_data()
        print("event stop recording")
        return 0
    

def ensure_dir(s):
    if not os.path.exists(s):
        os.makedirs(s)


def print_device_info(nodemap):
    """
    This function prints the device information of the camera from the transport
    layer; please see NodeMapInfo example for more in-depth comments on printing
    device information from the nodemap.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** DEVICE INFORMATION ***\n')

    try:
        result = True
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not readable.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def config_camera(nodemap):
    print("\n---------- CONFIG CAMERA ----------\n")
    try:
        result = True
        """------------------- 设置��像格式--------------------"""
        node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
        # 读出格式并print
        print(node_pixel_format.GetCurrentEntry().GetSymbolic())

        if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
            node_pixel_format_BayerRG8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('BayerRG8'))
            if PySpin.IsReadable(node_pixel_format_BayerRG8):
                pixel_format_BayerRG8 = node_pixel_format_BayerRG8.GetValue()
                node_pixel_format.SetIntValue(pixel_format_BayerRG8)

            else:
                print('Pixel format BayerRG8 8 not readable...')

        else:
            print('Pixel format not readable or writable...')

        """ -------------------- 设置ROI -------------------- """
        node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
        if not PySpin.IsAvailable(node_width) or not PySpin.IsWritable(node_width):
            print('\nUnable to set Width (integer retrieval). Aborting...\n')
            return False
        node_width.SetValue(WIDTH)

        node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
        if not PySpin.IsAvailable(node_height) or not PySpin.IsWritable(node_height):
            print('\nUnable to set Height (integer retrieval). Aborting...\n')
            return False
        node_height.SetValue(HEIGHT)

        node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
        if not PySpin.IsAvailable(node_offset_x) or not PySpin.IsWritable(node_offset_x):
            print('\nUnable to set Offset X (integer retrieval). Aborting...\n')
            return False
        node_offset_x.SetValue(OFFSET_X)
        
        node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
        if not PySpin.IsAvailable(node_offset_y) or not PySpin.IsWritable(node_offset_y):
            print('\nUnable to set Offset Y (integer retrieval). Aborting...\n')
            return False
        node_offset_y.SetValue(OFFSET_Y)


        """ -------------------- 设置曝光时间 -------------------- """
        if Auto_Exposure:
            # set AutoExposureExposureTimeUpperLimit is 500000
            node_exposure_time_upper_limit = PySpin.CFloatPtr(nodemap.GetNode('AutoExposureExposureTimeUpperLimit'))
            if not PySpin.IsReadable(node_exposure_time_upper_limit) or not PySpin.IsWritable(node_exposure_time_upper_limit):
                print('\nUnable to set Exposure Time Upper Limit (float retrieval). Aborting...\n')
                return False
            node_exposure_time_upper_limit.SetValue(5000000)
            
            # Turn on auto exposure
            node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
            if not PySpin.IsReadable(node_exposure_auto) or not PySpin.IsWritable(node_exposure_auto):
                print('\nUnable to set Exposure Auto (enumeration retrieval). Aborting...\n')
                return False
            entry_exposure_auto_on = node_exposure_auto.GetEntryByName('Continuous')
            if not PySpin.IsReadable(entry_exposure_auto_on):
                print('\nUnable to set Exposure Auto (entry retrieval). Aborting...\n')
                return False
            exposure_auto_on = entry_exposure_auto_on.GetValue()
            node_exposure_auto.SetIntValue(exposure_auto_on)
        else:
            # Turn off auto exposure
            node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
            if not PySpin.IsReadable(node_exposure_auto) or not PySpin.IsWritable(node_exposure_auto):
                print('\nUnable to set Exposure Auto (enumeration retrieval). Aborting...\n')
                return False
            entry_exposure_auto_off = node_exposure_auto.GetEntryByName('Off')
            if not PySpin.IsReadable(entry_exposure_auto_off):
                print('\nUnable to set Exposure Auto (entry retrieval). Aborting...\n')
                return False
            exposure_auto_off = entry_exposure_auto_off.GetValue()
            node_exposure_auto.SetIntValue(exposure_auto_off)
            # timed mode 
            node_exposure_mode = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureMode'))
            if not PySpin.IsReadable(node_exposure_mode) or not PySpin.IsWritable(node_exposure_mode):
                print('\nUnable to set Exposure Mode (enumeration retrieval). Aborting...\n')
                return False
            # node_exposure_mode.SetIntValue(PySpin.ExposureMode_Timed)
            entry_gain_auto_off = node_exposure_mode.GetEntryByName('Timed')
            if not PySpin.IsReadable(entry_gain_auto_off):
                print('\nUnable to set Gain Auto (entry retrieval). Aborting...\n')
                return False
            gain_auto_off = entry_gain_auto_off.GetValue()
            node_exposure_mode.SetIntValue(gain_auto_off)
            # Set exposure time
            node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
            if not PySpin.IsReadable(node_exposure_time) or not PySpin.IsWritable(node_exposure_time):
                print('\nUnable to set Exposure Time (float retrieval). Aborting...\n')
                return False
            # Set exposure time to 10000 us
            node_exposure_time.SetValue(EXPOSURE_TIME)
            print(f"exposure time is {node_exposure_time.GetValue()} us")
        # 显示曝光时间
        
#    
        """ -------------------- 设置增益 -------------------- """
        # Turn off auto gain
        node_gain_auto = PySpin.CEnumerationPtr(nodemap.GetNode('GainAuto'))
        if not PySpin.IsReadable(node_gain_auto) or not PySpin.IsWritable(node_gain_auto):
            print('\nUnable to set Gain Auto (enumeration retrieval). Aborting...\n')
            return False
        entry_gain_auto_off = node_gain_auto.GetEntryByName('Off')
        if not PySpin.IsReadable(entry_gain_auto_off):
            print('\nUnable to set Gain Auto (entry retrieval). Aborting...\n')
            return False
        gain_auto_off = entry_gain_auto_off.GetValue()
        node_gain_auto.SetIntValue(gain_auto_off)
        
        """ -------------------- 设置白平衡 -------------------- """
        # Turn off auto balance white
        node_balance_white_auto = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceWhiteAuto'))
        if not PySpin.IsReadable(node_balance_white_auto) or not PySpin.IsWritable(node_balance_white_auto):
            print('\nUnable to set Balance White Auto (enumeration retrieval). Aborting...\n')
            return False

        entry_balance_white_auto_off = node_balance_white_auto.GetEntryByName('Off')
        if not PySpin.IsReadable(entry_balance_white_auto_off):
            print('\nUnable to set Balance White Auto (entry retrieval). Aborting...\n')
            return False
        balance_white_auto_off = entry_balance_white_auto_off.GetValue()
        node_balance_white_auto.SetIntValue(balance_white_auto_off)

            
        # entry_balance_white_auto_on = node_balance_white_auto.GetEntryByName('Continuous')
        # if not PySpin.IsReadable(entry_balance_white_auto_on):
        #     print('\nUnable to set Balance White Auto (entry retrieval). Aborting...\n')
        #     return False
        # balance_white_auto_on = entry_balance_white_auto_on.GetValue()
        # node_balance_white_auto.SetIntValue(balance_white_auto_on)

        # 设置白平衡值 0-4
        # node_balance_selector = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceRatioSelector'))
        # if PySpin.IsReadable(node_balance_selector) and PySpin.IsWritable(node_balance_selector):
        #     # 选择Red通道
        #     entry_balance_red = node_balance_selector.GetEntryByName('Red')
        #     if PySpin.IsReadable(entry_balance_red):
        #         node_balance_selector.SetIntValue(entry_balance_red.GetValue())
                
        #         # 设置Red通道的白平衡比率
        #         node_balance_ratio = PySpin.CFloatPtr(nodemap.GetNode('BalanceRatio'))
        #         if PySpin.IsReadable(node_balance_ratio) and PySpin.IsWritable(node_balance_ratio):
        #             node_balance_ratio.SetValue(float(BALANCE_WHITE))
        # else:
        #     print('\nUnable to set Balance Ratio Selector. Skipping white balance settings...\n')
        
        """ -------------------- 设置吞吐量 -------------------- """
        node_device_link_throughput_limit = PySpin.CIntegerPtr(nodemap.GetNode('DeviceLinkThroughputLimit'))
        if not PySpin.IsReadable(node_device_link_throughput_limit) or not PySpin.IsWritable(node_device_link_throughput_limit):
            print('\nUnable to set Device Link Throughput Limit (integer retrieval). Aborting...\n')
            return False
        node_device_link_throughput_limit.SetValue(43000000)
        
        """ -------------------- 设置信号输入 -------------------- """
        if EX_Trigger:
            print("now is ex trigger \n")
            node_trigger_selector = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
            if not PySpin.IsAvailable(node_trigger_selector) or not PySpin.IsWritable(node_trigger_selector):
                print('\nUnable to set Trigger Selector (enumeration retrieval). Aborting...\n')
                return False
            entry_trigger_selector = node_trigger_selector.GetEntryByName('FrameStart')
            if not PySpin.IsAvailable(entry_trigger_selector) or not PySpin.IsReadable(entry_trigger_selector):
                print('\nUnable to enter Trigger Selector FrameStart. Aborting...\n')
                return False
            trigger_selector_framestart = entry_trigger_selector.GetValue()
            node_trigger_selector.SetIntValue(trigger_selector_framestart)
            

            node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
            if not PySpin.IsAvailable(node_trigger_source) or not PySpin.IsWritable(node_trigger_source):
                print('\nUnable to set Trigger Source (enumeration retrieval). Aborting...\n')
                return False
            entry_trigger_source_line3 = node_trigger_source.GetEntryByName('Line3')
            if not PySpin.IsAvailable(entry_trigger_source_line3) or not PySpin.IsReadable(entry_trigger_source_line3):
                print('\nUnable to enter Trigger Source Line3. Aborting...\n')
                return False
            trigger_source_line3 = entry_trigger_source_line3.GetValue()
            node_trigger_source.SetIntValue(trigger_source_line3)

            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            if not PySpin.IsAvailable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
                print('\nUnable to set Trigger Mode (enumeration retrieval). Aborting...\n')
                return False
            node_trigger_mode.SetIntValue(PySpin.TriggerMode_On)
            
            node_trigger_activation = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerActivation'))
            if not PySpin.IsAvailable(node_trigger_activation) or not PySpin.IsWritable(node_trigger_activation):
                print('\nUnable to set Trigger Activation (enumeration retrieval). Aborting...\n')
                return False
            entry_trigger_activation_risingedge = node_trigger_activation.GetEntryByName('RisingEdge')
            if not PySpin.IsAvailable(entry_trigger_activation_risingedge) or not PySpin.IsReadable(entry_trigger_activation_risingedge):
                print('\nUnable to enter Trigger Activation Rising Edge. Aborting...\n')
                return False
            trigger_activation_risingedge = entry_trigger_activation_risingedge.GetValue()
            node_trigger_activation.SetIntValue(trigger_activation_risingedge)

            node_trigger_overlap = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerOverlap'))
            if not PySpin.IsAvailable(node_trigger_overlap) or not PySpin.IsWritable(node_trigger_overlap):
                print('\nUnable to set Trigger Overlap (enumeration retrieval). Aborting...\n')
                return False
            node_trigger_overlap.SetIntValue(PySpin.TriggerOverlap_ReadOut)
        else:
            node_trigger_selector = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
            if not PySpin.IsAvailable(node_trigger_selector) or not PySpin.IsWritable(node_trigger_selector):
                print('\nUnable to set Trigger Selector (enumeration retrieval). Aborting...\n')
                return False
            entry_trigger_selector = node_trigger_selector.GetEntryByName('FrameStart')
            if not PySpin.IsAvailable(entry_trigger_selector) or not PySpin.IsReadable(entry_trigger_selector):
                print('\nUnable to enter Trigger Selector FrameStart. Aborting...\n')
                return False
            trigger_selector_framestart = entry_trigger_selector.GetValue()
            node_trigger_selector.SetIntValue(trigger_selector_framestart)

            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            if not PySpin.IsAvailable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
                print('\nUnable to set Trigger Mode (enumeration retrieval). Aborting...\n')
                return False
            node_trigger_mode.SetIntValue(PySpin.TriggerMode_Off)


            node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
            if not PySpin.IsReadable(node_trigger_source) or not PySpin.IsWritable(node_trigger_source):
                print('Unable to get trigger source (node retrieval). Aborting...')
                return False
            node_trigger_source_software = node_trigger_source.GetEntryByName('Software')
            if not PySpin.IsReadable(node_trigger_source_software):
                print('Unable to get trigger source (enum entry retrieval). Aborting...')
                return False
            node_trigger_source.SetIntValue(node_trigger_source_software.GetValue())
            print('Trigger source set to software...')

        """-----------------------设置捕获方式-------------------"""
        # Set acquisition mode to continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            print('\nUnable to set acquisition mode to multi-frame (enum retrieval). Aborting...\n')
            return False
        node_acquisition_mode.SetIntValue(PySpin.AcquisitionMode_Continuous)


        """ -------------------- 设置帧率 -------------------- """
        node_framerate_enable = PySpin.CBooleanPtr(nodemap.GetNode('AcquisitionFrameRateEnable'))
        if not PySpin.IsAvailable(node_framerate_enable) or not PySpin.IsWritable(node_framerate_enable):
            print('\nUnable to enable Framerate (boolean retrieval). Aborting...\n')
            return False
        node_framerate_enable.SetValue(True)
            
        node_acquisition_framerate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
        if not PySpin.IsReadable(node_acquisition_framerate) or not PySpin.IsWritable(node_acquisition_framerate):
            print('\nUnable to set Framerate (float retrieval). Aborting...\n')
            return False
        node_acquisition_framerate.SetValue(FRAMERATE)
        
        """ -------------------- 设置数据块 -------------------- """
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))
        if not PySpin.IsWritable(chunk_mode_active):
            print('\nUnable to activate Chunk Mode (boolean retrieval). Aborting...\n')
            return False
        chunk_mode_active.SetValue(True)
        
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))
        if not PySpin.IsReadable(chunk_selector) or not PySpin.IsWritable(chunk_selector):
            print('\nUnable to retrieve Chunk Selector (enumeration retrieval). Aborting...\n')
            return False
        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]
        
        print('Enabling entries...')
        # Iterate through our list and select each entry node to enable
        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
            chunk_str = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Enable the boolean, thus enabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_str))
                result = False
            elif chunk_enable.GetValue() is True:
                print('{} enabled'.format(chunk_str))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(True)
                print('{} enabled'.format(chunk_str))
            else:
                print('{} not writable'.format(chunk_str))

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False
    return result


def disable_chunk_data(nodemap):
    """
    This function disables each type of chunk data before disabling chunk data mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise
    :rtype: bool
    """
    try:
        result = True

        # Retrieve the selector node
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))

        if not PySpin.IsReadable(chunk_selector) or not PySpin.IsWritable(chunk_selector):
            print('Unable to retrieve chunk selector. Aborting...\n')
            return False

        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]

        print('Disabling entries...')

        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())

            chunk_symbolic_form = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Disable the boolean, thus disabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_symbolic_form))
                result = False
            elif not chunk_enable.GetValue():
                print('{} disabled'.format(chunk_symbolic_form))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(False)
                print('{} disabled'.format(chunk_symbolic_form))
            else:
                print('{} not writable'.format(chunk_symbolic_form))

        # Deactivate Chunk Mode
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))

        if not PySpin.IsWritable(chunk_mode_active):
            print('Unable to deactivate chunk mode. Aborting...\n')
            return False

        chunk_mode_active.SetValue(False)

        print('Chunk mode deactivated...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def reset_trigger(nodemap):
    """
    This function returns the camera to a normal state by turning off trigger mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if not PySpin.IsReadable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
            print('Unable to disable trigger mode (node retrieval). Aborting...')
            return False

        node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
        if not PySpin.IsReadable(node_trigger_mode_off):
            print('Unable to disable trigger mode (enum entry retrieval). Aborting...')
            return False

        node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())

        print('Trigger mode disabled...')

        node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
        if not PySpin.IsReadable(node_trigger_source) or not PySpin.IsWritable(node_trigger_source):
            print('Unable to get trigger source (node retrieval). Aborting...')
            return False
        node_trigger_source_software = node_trigger_source.GetEntryByName('Software')
        if not PySpin.IsReadable(node_trigger_source_software):
            print('Unable to get trigger source (enum entry retrieval). Aborting...')
            return False
        node_trigger_source.SetIntValue(node_trigger_source_software.GetValue())
        print('Trigger source set to software...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def enbale_trigger(nodemap):
    """
    This function returns the camera to a normal state by turning on trigger mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if not PySpin.IsReadable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
            print('Unable to disable trigger mode (node retrieval). Aborting...')
            return False
        node_trigger_mode.SetIntValue(PySpin.TriggerMode_On)

        print('Trigger mode enabled...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def read_chunk_data(image):
    """
    This function displays a select amount of chunk data from the image. Unlike
    accessing chunk data via the nodemap, there is no way to loop through all
    available data.

    :param image: Image to acquire chunk data from
    :type image: Image object
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        chunk_data = image.GetChunkData()
        exposure_time = chunk_data.GetExposureTime()
        timestamp = chunk_data.GetTimestamp()
    
    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False
    return result, exposure_time, timestamp



def acquire_images(cam, nodemap, path):
    print('*** IMAGE ACQUISITION ***\n')
    try:
        # 预分配内存
        images = np.empty((NUM_IMAGES, HEIGHT, WIDTH), dtype=np.uint8)
        timestamps = np.zeros(NUM_IMAGES, dtype=np.uint64)
        exposure_times = np.zeros(NUM_IMAGES, dtype=float)
        
        # 创建图像处理器
        # processor = PySpin.ImageProcessor()
        # processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        global running
        for i in range(NUM_IMAGES):
            if not running:
                break
            try:
                image_result = cam.GetNextImage(1000)
                
                if image_result.IsIncomplete():
                    print(f'Image incomplete with status {image_result.GetImageStatus()}')
                    image_result.Release()
                    continue
                
                # 直接获取图像数据并转换
                # converted = processor.Convert(image_result, PySpin.PixelFormat_RGB8)
                #这里需要保存原始的RG8数据，raw文件
                images[i] = image_result.GetNDArray()
                
                # 读取时间戳等信息
                _, exposure_times[i], timestamps[i] = read_chunk_data(image_result)
                # print(f"exposure time is {exposure_times[i]} us")
                image_result.Release()
                
            except PySpin.SpinnakerException as ex:
                print(f'Error: {ex}')
                return False
        
        # 结束采集
        cam.EndAcquisition()
        global acquisition_flag
        acquisition_flag = 1

        # 创建保存预览图片的目录
        preview_dir = os.path.join(path, "preview_images")
        ensure_dir(preview_dir)

        # 创建单个文件存储所有图像
        filename = os.path.join(path, "images.raw")
        with open(filename, 'wb') as f:
            # 写入图像数量和ROI信息作为文件头
            header = np.array([
                NUM_IMAGES,  # 图像数量
                OFFSET_X, OFFSET_Y, WIDTH, HEIGHT  # ROI信息
            ], dtype=np.int32)
            f.write(header.tobytes())
            
            # 连续写入所有图像数据,并每10张保存一张预览图
            for idx, img_data in enumerate(images):
                f.write(img_data.tobytes())
                
                # 每10张图像保存一张预览图
                if idx % 10 == 0:
                    # 将BayerRG8格式转换为RGB
                    rgb_image = cv.cvtColor(img_data, cv.COLOR_BayerRG2RGB)
                    # 保存图像
                    cv.imwrite(os.path.join(preview_dir, f'preview_{idx}.png'), cv.cvtColor(rgb_image, cv.COLOR_RGB2BGR))

        # 保存时间戳和曝光时间
        np.savetxt(os.path.join(path, 'exposure_times.txt'), exposure_times)
        np.savetxt(os.path.join(path, 'timestamps.txt'), timestamps)
        
        return True
        
    except PySpin.SpinnakerException as ex:
        print(f'Error: {ex}')
        return False
    


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
    global cam_list, system
    result = True
    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Get current library version
    version = system.GetLibraryVersion()
    print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()

    num_cameras = cam_list.GetSize()

    print('Number of cameras detected: %d' % num_cameras)

    # Finish if there are no cameras
    if num_cameras == 0:
        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        # input('Done! Press Enter to exit...')
        return False
    

    ## config prophesee camera
    path = os.path.abspath(os.path.join('./', time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())))
    ensure_dir(path) 
    prophesee_cam = event(0,path)
    prophesee_cam.config_prophesee()
    # Run example on each camera
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)
        try:
            result = True

            # Retrieve TL device nodemap and print device information
            nodemap_tldevice = cam.GetTLDeviceNodeMap()

            # result &= print_device_info(nodemap_tldevice)

            # Initialize camera
            cam.Init()
            print("init")
            # Retrieve GenICam nodemap
            nodemap = cam.GetNodeMap()

            # Configure camera
            if config_camera(nodemap) is False:
                cam.DeInit()
                cam_list.Clear()
                system.ReleaseInstance() 
                return False
            # acquire images  flag 
            global acquisition_flag

            acquisition_flag = 0
            #  Begin acquiring images
            cam.BeginAcquisition()
            # 多线程配置 
            print("线程开始")
            prophesee_thread = Thread(target=prophesee_cam.start_recording,args=()) 

            flir_thread = Thread(target=acquire_images,args=(cam,nodemap,path))

            #多线程启动
            prophesee_thread.start()
            flir_thread.start()
            ##-------------  发送指令  --------—--------##

            # 示例：发送产生NUM_IMAGES个频率为FRAMERATE Hz脉冲的指令  
            send_pulse_command(NUM_IMAGES,FRAMERATE)
            # 关闭串口  
            ser.close()

            ##-----------------------------------------##
            prophesee_thread.join()
            flir_thread.join()
            # 将存放都放在了 acquire 函数里
            try : 
                acquisition_flag = 0 # 结束了采集
                prophesee_cam.prophesee_tirgger_found()
            except :
                print("save is wrong")
            # Disable chunk data
            result &= disable_chunk_data(nodemap)
        
            # Reset trigger
            result &= reset_trigger(nodemap)

            
            # Deinitialize camera
            cam.DeInit()

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
            cam.DeInit()
        
        print('Camera %d example complete... \n' % i)

    cam_list.Clear()
    del cam
    system.ReleaseInstance()
    return result


if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)

