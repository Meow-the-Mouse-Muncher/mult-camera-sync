import PySpin
import sys
import time
import os
import sys
import tkinter as tk
import tkinter.font as tkf
import threading
# import pigpio
import cv2
import numpy as np
from os import path
import signal

#  flir camera set
NUM_IMAGES = 20  # number of images to save

FRAMERATE = int(15) # fps
EXPOSURE_TIME = 50000 # us
Auto_Exposure = False   #自动曝光设置
EX_Trigger = False      #触发方式设置
expose_time = EXPOSURE_TIME #us
frequency =int(FRAMERATE) # 设置频率


OFFSET_X = 0#224
OFFSET_Y = 0#524
WIDTH = 2000
HEIGHT = 1000

global cam_list, system

def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Cleaning up...')
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
        """------------------- 设置图像格式--------------------""" 
        node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
        if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
            node_pixel_format_BayerRG8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('BayerRG8'))
            if PySpin.IsReadable(node_pixel_format_BayerRG8):
                # Retrieve the integer value from the entry node
                pixel_format_BayerRG8 = node_pixel_format_BayerRG8.GetValue()

                # Set integer as new value for enumeration node
                node_pixel_format.SetIntValue(pixel_format_BayerRG8)

                print('Pixel format set to %s...' % node_pixel_format.GetCurrentEntry().GetSymbolic())

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

        """-----------------------设置捕获方式-------------------"""
        # Set acquisition mode to continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            print('\nUnable to set acquisition mode to multi-frame (enum retrieval). Aborting...\n')
            return False
        node_acquisition_mode.SetIntValue(PySpin.AcquisitionMode_Continuous)


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
        global cam_list, system
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

        # Retrieve entries
        #
        # *** NOTES ***
        # PySpin handles mass entry retrieval in a different way than the C++
        # API. Instead of taking in a NodeList_t reference, GetEntries() takes
        # no parameters and gives us a list of INodes. Since we want these INodes
        # to be of type CEnumEntryPtr, we can use a list comprehension to
        # transform all of our collected INodes into CEnumEntryPtrs at once.
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

def acquire_images(cam, nodemap):
    try:
        # 预分配内存
        images = np.empty((NUM_IMAGES, HEIGHT, WIDTH,3), dtype=np.uint8)
        exposure_times = np.zeros(NUM_IMAGES, dtype=np.float64)
        timestamps = np.zeros(NUM_IMAGES, dtype=np.uint64)
        processor = PySpin.ImageProcessor()
        processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        # 配置相机缓冲
        cam.BeginAcquisition()
        
        for i in range(NUM_IMAGES):
            try:
                # 获取图像
                image_result = cam.GetNextImage(1000)
                
                if image_result.IsIncomplete():
                    continue
                    
                # 直接写入预分配的数组，避免复制
                chunk_data = image_result.GetChunkData()
                exposure_times[i] = chunk_data.GetExposureTime()
                timestamps[i] = chunk_data.GetTimestamp()
                images[i] = processor.Convert(image_result, PySpin.PixelFormat_RGB8).GetNDArray()
 
                
                image_result.Release()
                
            except PySpin.SpinnakerException as ex:
                print(f'Error: {ex}')
                continue
                
        cam.EndAcquisition()
        return True, images, exposure_times, timestamps
        
    except PySpin.SpinnakerException as ex:
        global cam_list, system
        for cam in cam_list:
            try:
                cam.EndAcquisition()
                cam.DeInit()
            except:
                pass
        cam_list.Clear()
        system.ReleaseInstance()
        print(f'Error: {ex}')
        return False, None, None, None


def save_images(images, exposure_times, timestamps, path):
    print('start saving images...')
    et_txt = open(os.path.join(path, 'exposure_times.txt'), 'w')
    ts_txt = open(os.path.join(path, 'timestamps.txt'), 'w')
    
    for i in range(len(images)):
        et_txt.write('%s\n' % exposure_times[i])
        ts_txt.write('%s\n' % timestamps[i])
        filename = os.path.join(path, str(i).rjust(5, '0') + ".png")
        
        # 使用 OpenCV 保存图像
        cv2.imwrite(filename, images[i])
        

    
    et_txt.close()
    ts_txt.close()
    return True


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
    global cam_list, system
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
        input('Done! Press Enter to exit...')
        return False

    

    current_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(current_dir, time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())))

    print('Images will be saved at %s' % path)
    ensure_dir(path) 


    # Run example on each camera
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)
        try:
            result = True

            # Retrieve TL device nodemap and print device information
            nodemap_tldevice = cam.GetTLDeviceNodeMap()

            result &= print_device_info(nodemap_tldevice)

            # Initialize camera
            cam.Init()

            # Retrieve GenICam nodemap
            nodemap = cam.GetNodeMap()

            # Configure camera
            if config_camera(nodemap) is False:
                cam.DeInit()
                cam_list.Clear()
                system.ReleaseInstance() 
                return False
            # Acquire images
            result, images, exposure_times, timestamps = acquire_images(cam, nodemap)

            # Save image    
            result &= save_images(images, exposure_times, timestamps, path)
            
            # Disable chunk data
            result &= disable_chunk_data(nodemap)
            
            # Reset trigger
            result &= reset_trigger(nodemap)
            
            # Deinitialize camera
            cam.DeInit()

        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False



        print('Camera %d example complete... \n' % i)

    # Release reference to camera
    # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
    # cleaned up when going out of scope.
    # The usage of del is preferred to assigning the variable to None.
    del cam

    # Clear camera list before releasing system
    cam_list.Clear()

    # Release system instance
    system.ReleaseInstance()

    # input('Done! Press Enter to exit...')
    return result


if __name__ == '__main__':
    main()
