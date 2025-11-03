import PySpin
import sys
import time
import os
import Jetson.GPIO as GPIO
import sys
import tkinter as tk
import tkinter.font as tkf
from threading import Thread
import numpy as np
import cv2 as cv
sys.path.append("/home/sai/openeb/sdk/modules/core/python/pypkg")
sys.path.append("/home/sai/openeb/build/py3")
#逐行输出sys.path内容
# print('\n'.join(sys.path))

from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device

#  flir camera set
#prophesee first trigger is incompelete, so we save one more image
# evk4 触发反向了
## flir camera set
FRAMERATE = int(15) # fps
EXPOSURE_TIME = 50000 # us
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
# prophesee camera set
stc_filter_ths = 10000  # Length of the time window for filtering (in us)
stc_cut_trail = True  # If true, after an event goes through, it removes all events until change of polarity
#全局变量  
nameoutglob = 1
acquisition_flag = 0   # 保证 evk4 的采集
# 硬件裁剪
roi_x0 = int(340)
roi_y0 = int(60)
roi_x1 = int(939)
roi_y1 = int(659)


expose_time = EXPOSURE_TIME #us
frequency =int(FRAMERATE) # 设置频率
duty_cycle = 50 # 设置占空比为50
trigger_io = 11
GPIO.setmode(GPIO.BOARD)
# GPIO.setup(trigger_io, GPIO.OUT, initial=GPIO.LOW)
# trigger_flag = 0

def trigger_star(out_io,fre,duty_cycle):
    GPIO.setup(out_io, GPIO.OUT, initial=GPIO.LOW)
    pwm = GPIO.PWM(out_io, fre)	# 50Hz
    pwm.start(duty_cycle)	# 占空比为50%

    # 等待1秒
    time.sleep(1)

    pwm.stop()
    GPIO.cleanup()


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
        height, width = mv_iterator.get_size()  # Camera Geometry
        print(f"height = {height}, width = {width}")
        global acquisition_flag
        for evs in mv_iterator:
            if acquisition_flag == 1:
                break
        return 0
    def stop_recording(self):
        self.ieventstream.stop_log_raw_data()
        print("stop recording")
        del self.device

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

        """ -------------------- 设置曝光时间 -------------------- """
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

#
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

def acquire_images(cam, nodemap,path):
    """
    This function acquires and saves 10 images from a device.
    Please see Acquisition example for more in-depth comments on acquiring images.

    :param cam: Camera to acquire images from.
    :param nodemap: Device nodemap.
    :type cam: CameraPtr
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** IMAGE ACQUISITION ***\n')
    try:
        result = True


        # #  Begin acquiring images
        # cam.BeginAcquisition()

        # Retrieve, convert, and save images

        # Create ImageProcessor instance for post processing images
        processor = PySpin.ImageProcessor()
        
        # Set default image processor color processing method
        #
        # *** NOTES ***
        # By default, if no specific color processing algorithm is set, the image
        # processor will default to NEAREST_NEIGHBOR method.
        processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        i = 0
        print('start saving images...')
        et_txt = open(os.path.join(path, 'exposure_times.txt'), 'w')
        ts_txt = open(os.path.join(path, 'timestamps.txt'), 'w')
        while(1):
            try:
                # Retrieve next received image and ensure image completion
                # By default, GetNextImage will block indefinitely until an image arrives.
                # In this example, the timeout value is set to [exposure time + 1000]ms to ensure that an image has enough time to arrive under normal conditions
                image_result = cam.GetNextImage()
                
                if image_result.IsIncomplete():
                    print('Image incomplete with image status %d...' % image_result.GetImageStatus())
                    # we need to release the image
                    image_result.Release()
                    continue

                else:
                    # Print image information
                    width = image_result.GetWidth()
                    height = image_result.GetHeight()
                    print('Grabbed Image %d, width = %d, height = %d' % (i, width, height))
                    
                    # Read chunk data
                    result, exposure_time, timestamp = read_chunk_data(image_result)
                    
                    # Convert image to RGB8
                    image = processor.Convert(image_result, PySpin.PixelFormat_RGB8).GetNDArray()

                    
                    
                # Release image
                image_result.Release()
                # 丢弃第一张图片
                if i > 0:
                        et_txt.write('%s\n' % exposure_time)
                        ts_txt.write('%s\n' % timestamp)
                        filename = os.path.join(path, f'image_{i:06d}.png')
                        image = np.array(image)
                        cv.imwrite(filename, image)
                i += 1
            except PySpin.SpinnakerException as ex:
                print('Error: %s' % ex)
                return False
        et_txt.close()
        ts_txt.close()
        print('end saving images...')
        
        # End acquisition
        print(f'we acquiring {i} images')
        cam.EndAcquisition()
        

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result

def save_images(images, exposure_times, timestamps, path):
    print('start saving images...')
    et_txt = open(os.path.join(path, 'exposure_times.txt'), 'w')
    ts_txt = open(os.path.join(path, 'timestamps.txt'), 'w')
    for i in range(len(images)):
        et_txt.write('%s\n' % exposure_times[i])
        ts_txt.write('%s\n' % timestamps[i])
        # filename = os.path.join(path, str(i).rjust(5, '0') + ".png")
        # images[i].Save(filename)
    # 丢弃第一张图片
    print(f'total {len(images)} images')
    images[:] = images[1:] 
    print(f'after discarding first image, we have {len(images)} images')
    index = len(images)//2
    filename = os.path.join(path, 'image_center.png')
    cv.imwrite(filename, images[index])
    images = np.array(images)
    filename = os.path.join(path, 'image')
    np.save(filename,images)
    et_txt.close()
    ts_txt.close()
    print('end saving images...')
    return True 

def save_list_to_avi(nodemap, nodemap_tldevice, images,path):
    """
    This function prepares, saves, and cleans up an AVI video from a vector of images.

    :param nodemap: Device nodemap.
    :param nodemap_tldevice: Transport layer device nodemap.
    :param images: List of images to save to an AVI video.
    :type nodemap: INodeMap
    :type nodemap_tldevice: INodeMap
    :type images: list of ImagePtr
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    print('*** CREATING VIDEO ***')

    try:
        result = True

        # Retrieve device serial number for filename
        device_serial_number = ''
        node_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))

        if PySpin.IsReadable(node_serial):
            device_serial_number = node_serial.GetValue()
            print('Device serial number retrieved as %s...' % device_serial_number)

        # Get the current frame rate; acquisition frame rate recorded in hertz
        #
        # *** NOTES ***
        # The video frame rate can be set to anything; however, in order to
        # have videos play in real-time, the acquisition frame rate can be
        # retrieved from the camera.

        node_acquisition_framerate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))

        if not PySpin.IsReadable(node_acquisition_framerate):
            print('Unable to retrieve frame rate. Aborting...')
            return False

        framerate_to_set = node_acquisition_framerate.GetValue()

        print('Frame rate to be set to %.2f...' % framerate_to_set)

        # Select option and open AVI filetype with unique filename
        #
        # *** NOTES ***
        # Depending on the filetype, a number of settings need to be set in
        # an object called an option. An uncompressed option only needs to
        # have the video frame rate set whereas videos with MJPG or H264
        # compressions should have more values set.
        #
        # Once the desired option object is configured, open the AVI file
        # with the option in order to create the image file.
        #
        # Note that the filename does not need to be appended to the
        # name of the file. This is because the AVI recorder object takes care
        # of the file extension automatically.
        #
        # *** LATER ***
        # Once all images have been added, it is important to close the file -
        # this is similar to many other standard file streams.

        avi_recorder = PySpin.SpinVideo()

        if chosenAviType == AviType.UNCOMPRESSED:
            avi_filename = os.path.join(path, 'SaveToAvi-UNCOMPRESSED')

            option = PySpin.AVIOption()
            option.frameRate = framerate_to_set
            option.height = images[0].GetHeight()
            option.width = images[0].GetWidth()

        elif chosenAviType == AviType.MJPG:
            avi_filename = os.path.join(path, 'SaveToAvi-MJPG')

            option = PySpin.MJPGOption()
            option.frameRate = framerate_to_set
            option.quality = 75
            option.height = images[0].GetHeight()
            option.width = images[0].GetWidth()

        elif chosenAviType == AviType.H264:
            avi_filename = os.path.join(path, 'SaveToAvi-H264')

            option = PySpin.H264Option()
            option.frameRate = framerate_to_set
            option.bitrate = 1000000
            option.height = images[0].GetHeight()
            option.width = images[0].GetWidth()

        else:
            print('Error: Unknown AviType. Aborting...')
            return False

        avi_recorder.Open(avi_filename, option)

        # Construct and save AVI video
        #
        # *** NOTES ***
        # Although the video file has been opened, images must be individually
        # appended in order to construct the video.
        print('Appending %d images to AVI file: %s.avi...' % (len(images), avi_filename))

        for i in range(len(images)):
            avi_recorder.Append(images[i])
            print('Appended image %d...' % i)

        # Close AVI file
        #
        # *** NOTES ***
        # Once all images have been appended, it is important to close the
        # AVI file. Notice that once an AVI file has been closed, no more
        # images can be added.

        avi_recorder.Close()
        print('Video saved at %s.avi' % avi_filename)

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result



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
    path = os.path.join('./data', time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))
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

            result &= print_device_info(nodemap_tldevice)

            # Initialize camera
            cam.Init()
            # Retrieve GenICam nodemap
            nodemap = cam.GetNodeMap()
            # Configure camera
            if config_camera(nodemap) is False:
                return False
            # acquire images
            global acquisition_flag
            acquisition_flag = 0
            #  Begin acquiring images
            cam.BeginAcquisition()
            #pip pwm config
            try:
                print("pigpiod is running")
            except:
                print("pigpiod is not running")


            # 多线程执行 
            print("线程开始")
            prophesee_thread = Thread(target=prophesee_cam.start_recording,args=()) 
            prophesee_thread.start()
            # pwm generate
            GPIO.setup(trigger_io, GPIO.OUT, initial=GPIO.LOW)
            pwm = GPIO.PWM(trigger_io, frequency)	# 50Hz
            pwm.start(duty_cycle)	# 占空比为50%
            result = acquire_images(cam, nodemap,path)
            pwm.stop()
            GPIO.cleanup()

            acquisition_flag = 1
            prophesee_cam.stop_recording()
            prophesee_cam.prophesee_tirgger_found()

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
    # Clear camera list before releasing system
    cam_list.Clear()
    del cam
    # Release system instance
    system.ReleaseInstance()

    # input('Done! Press Enter to exit...')
    return result


if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)

