import os
import PySpin
import sys
import tkinter as tk
import tkinter.font as tkf
import cv2
from threading import Thread
import numpy as np
from queue import Queue
############  696 crop

class TriggerType:
    SOFTWARE = 1
    HARDWARE = 2
### 一些存储
name_out = str(1)
images_m = []
images_s = []
timestamps_m = []
timestamps_s = []
MASTERNODE = None
savestyle = 4
### 一些参数配置
## FLIR从相机
CHOSEN_TRIGGER = TriggerType.HARDWARE
#NUM_IMAGES_S = 200
NUM_SEQ = 3
# width_s = 2048
# height_s = 1536
width_s = 1000
height_s = 1000
offx_s = 0
offy_s = 0
#exposure_time_s = [1500,300,900] # 2 0 1
#timeout = int((exposure_time_s[0] / 1000) + 1000)
framerate_m = 20.0

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

class FLIRTYPE:
    MASTER = 0
    SLAVE = 1

class FLIR():
    def __init__(self, cam):
        self.cam = cam
        self.device_number = self.get_device_number()
        self.cam.Init()
        self.nodemap = cam.GetNodeMap()
        self.initSlave(NUM_IMAGES_S, NUM_SEQ, width_s, height_s, offx_s, offy_s, exposure_time_s, timeout)


    def initSlave(self, num_images, num_sequences, width, height, offx, offy, exposureTime, timeout):
        self.FlirType = FLIRTYPE.SLAVE
        self.PixelFormat = 'RGB8Packed'
        self.ColorSpace = cv2.COLOR_BAYER_RG2RGB_VNG
        self.Images = Queue()
        self.TimeStamps = []
        self.NUM_IMAGES = num_images
        self.NUM_SEQ = num_sequences
        self.Width = width
        self.Height = height
        self.Offx = offx
        self.Offy = offy
        self.ExposureTime = exposureTime
        self.Gain = 20
        self.TimeOut = timeout
        self.SaveImgFile = './Master'
        self.FrameRate = framerate_m

    def deinit(self):
        self.cam.DeInit()

    def get_device_number(self):
        nodemap_tldevice = self.cam.GetTLDeviceNodeMap()
        device_serial_number = ''
        node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
        if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
            device_serial_number = node_device_serial_number.GetValue()
            print('Device serial number retrieved as %s...' % device_serial_number)
        return device_serial_number

    def displayValue(self, node, value):
        if self.FlirType == FLIRTYPE.MASTER:
            print("MASTER: "+ node +" set to "+ value + "\n")
        else:
            print("SLAVE : "+ node +" set to "+ value + "\n")

    def displayErr(self, node):
        if self.FlirType == FLIRTYPE.MASTER:
            print("MASTER: "+ node +" is not available\n")
        else:
            print("SLAVE : "+ node +" is not available\n")


    def config_HDR_camera(self):
        print("\n-----CONFIG MASTER CAMERA-----\n")
        try:
            result = True
            node_pixel_format = PySpin.CEnumerationPtr(self.nodemap.GetNode('PixelFormat'))
            if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
                node_pixel_format_value = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName(self.PixelFormat))
                if PySpin.IsAvailable(node_pixel_format_value) and PySpin.IsReadable(node_pixel_format_value):
                    pixel_format_value = node_pixel_format_value.GetValue()
                    node_pixel_format.SetIntValue(pixel_format_value)
                    self.displayValue('PixelFormat',node_pixel_format.GetCurrentEntry().GetSymbolic())
                else:
                    self.displayErr('PixelFormat')
            else:
                self.displayErr('PixelFormat')

            # 设置auto gain off
            node_gain_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('GainAuto'))
            if not PySpin.IsAvailable(node_gain_auto) or not PySpin.IsWritable(node_gain_auto):
                self.displayErr('GainAuto')
                return False
            entry_gain_auto_off = node_gain_auto.GetEntryByName('Off')
            if not PySpin.IsAvailable(entry_gain_auto_off):
                self.displayErr('GainAutoOff')
                return False
            gain_auto_off = entry_gain_auto_off.GetValue()
            node_gain_auto.SetIntValue(gain_auto_off)

            # 设置gain;
            node_gain = PySpin.CFloatPtr(self.nodemap.GetNode('Gain'))
            if not PySpin.IsAvailable(node_gain) or not PySpin.IsWritable(node_gain):
                self.displayErr('Gain')
                return False
            node_gain.SetValue(self.Gain)

            # Line Selector    Line 2
            node_line_selector = PySpin.CEnumerationPtr(self.nodemap.GetNode('LineSelector'))
            if not PySpin.IsAvailable(node_line_selector) or not PySpin.IsWritable(node_line_selector):
                self.displayErr('LineSelector')
                return False
            entry_line_selector_line2 = node_line_selector.GetEntryByName('Line2')
            if not PySpin.IsAvailable(entry_line_selector_line2) or not PySpin.IsReadable(entry_line_selector_line2):
                self.displayErr('LineSelector')
                return False
            line_selector_line2 = entry_line_selector_line2.GetValue()
            node_line_selector.SetIntValue(line_selector_line2)
            self.displayValue('LineSelector','Line2')
            # Line Mode        Output
            node_line_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('LineMode'))
            if not PySpin.IsAvailable(node_line_mode) or not PySpin.IsWritable(node_line_mode):
                self.displayErr('LineMode')
                return False
            entry_line_mode_output = node_line_mode.GetEntryByName('Output')
            if not PySpin.IsAvailable(entry_line_mode_output) or not PySpin.IsReadable(entry_line_mode_output):
                self.displayErr('LineMode')
                return False
            line_mode_output = entry_line_mode_output.GetValue()
            node_line_mode.SetIntValue(line_mode_output)
            self.displayValue('LineMode','Output')
            # Line Source      Exposure Active
            node_line_source = PySpin.CEnumerationPtr(self.nodemap.GetNode('LineSource'))
            if not PySpin.IsAvailable(node_line_source) or not PySpin.IsWritable(node_line_source):
                self.displayErr('LineSource')
                return False
            entry_line_source_exposureactive = node_line_source.GetEntryByName('ExposureActive')
            if not PySpin.IsAvailable(entry_line_source_exposureactive) \
                    or not PySpin.IsReadable(entry_line_source_exposureactive):
                self.displayErr('LineSource')
                return False
            line_source_exposureactive = entry_line_source_exposureactive.GetValue()
            node_line_source.SetIntValue(line_source_exposureactive)
            self.displayValue('LineSource','ExposureActive')
            # 使能图像帧率修改
            node_frameRate_En = PySpin.CBooleanPtr(
                self.nodemap.GetNode('AcquisitionFrameRateEnable'))
            if PySpin.IsAvailable(node_frameRate_En) and PySpin.IsWritable(node_frameRate_En):
                node_frameRate_En.SetValue(True)
                self.displayValue('FrameRateEnable',format(node_frameRate_En.GetValue()))
            else:
                self.displayErr('FrameRateEnable')
            # 图像帧率
            node_acquisition_framerate = PySpin.CFloatPtr(
                self.nodemap.GetNode('AcquisitionFrameRate'))
            if PySpin.IsAvailable(node_acquisition_framerate) and PySpin.IsWritable(node_acquisition_framerate):
                node_acquisition_framerate.SetValue(self.FrameRate)
                self.displayValue('FrameRate',format(node_acquisition_framerate.GetValue()))
            else:
                self.displayValue('FrameRate',format(node_acquisition_framerate.GetValue()))
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            return False
        return result

    def init_sequencer(self):
        try:
            result = True
            node_sequencer_configuration_valid = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerConfigurationValid'))
            if not PySpin.IsAvailable(node_sequencer_configuration_valid) \
                    or not PySpin.IsReadable(node_sequencer_configuration_valid):
                self.displayErr('SequencerConfigurationValid')
                return False
            sequencer_configuration_valid_yes = node_sequencer_configuration_valid.GetEntryByName('Yes')
            if not PySpin.IsAvailable(sequencer_configuration_valid_yes) \
                    or not PySpin.IsReadable(sequencer_configuration_valid_yes):
                self.displayErr('SequencerConfigurationValid Yes')
                return False
            node_sequencer_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerMode'))
            if node_sequencer_configuration_valid.GetCurrentEntry().GetValue() == \
                    sequencer_configuration_valid_yes.GetValue():
                if not PySpin.IsAvailable(node_sequencer_mode) or not PySpin.IsWritable(node_sequencer_mode):
                    self.displayErr('SequencerMode')
                    return False
                sequencer_mode_off = node_sequencer_mode.GetEntryByName('Off')
                if not PySpin.IsAvailable(sequencer_mode_off) or not PySpin.IsReadable(sequencer_mode_off):
                    self.displayErr('SequencerMode Off')
                    return False
                node_sequencer_mode.SetIntValue(sequencer_mode_off.GetValue())
            self.displayValue('Sequencer mode','disabled')
            # 关闭自动曝光
            node_exposure_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('ExposureAuto'))
            if not PySpin.IsAvailable(node_exposure_auto) or not PySpin.IsWritable(node_exposure_auto):
                self.displayErr('ExposureAuto')
                return False
            exposure_auto_off = node_exposure_auto.GetEntryByName('Off')
            if not PySpin.IsAvailable(exposure_auto_off) or not PySpin.IsReadable(exposure_auto_off):
                self.displayErr('ExposureAuto Off')
                return False
            node_exposure_auto.SetIntValue(exposure_auto_off.GetValue())
            self.displayValue('Automatic exposure','disabled')

            # 开启Seq配置模式
            node_sequencer_configuration_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerConfigurationMode'))
            if not PySpin.IsAvailable(node_sequencer_configuration_mode) \
                    or not PySpin.IsWritable(node_sequencer_configuration_mode):
                self.displayErr('SequencerConfigurationMode')
                return False
            sequencer_configuration_mode_on = node_sequencer_configuration_mode.GetEntryByName('On')
            if not PySpin.IsAvailable(sequencer_configuration_mode_on)\
                    or not PySpin.IsReadable(sequencer_configuration_mode_on):
                self.displayErr('SequencerConfigurationMode On')
                return False
            node_sequencer_configuration_mode.SetIntValue(sequencer_configuration_mode_on.GetValue())
            self.displayValue('Sequencer configuration mode','enabled')
        except PySpin.SpinnakerException as ex:
            print('Error: {}'.format(ex))
            result = False
        return result

    def open_sequencer(self):
        try:
            result = True
            # Turn configuration mode off
            node_sequencer_configuration_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerConfigurationMode'))
            if not PySpin.IsAvailable(node_sequencer_configuration_mode) \
                    or not PySpin.IsWritable(node_sequencer_configuration_mode):
                self.displayErr('SequencerConfigurationMode')
                return False
            sequencer_configuration_mode_off = node_sequencer_configuration_mode.GetEntryByName('Off')
            if not PySpin.IsAvailable(sequencer_configuration_mode_off)\
                    or not PySpin.IsReadable(sequencer_configuration_mode_off):
                self.displayErr('SequencerConfigurationMode  Off')
                return False
            node_sequencer_configuration_mode.SetIntValue(sequencer_configuration_mode_off.GetValue())
            self.displayValue('SequencerConfigurationMode','disabled')
            # Turn sequencer mode on
            node_sequencer_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerMode'))
            if not PySpin.IsAvailable(node_sequencer_mode) or not PySpin.IsWritable(node_sequencer_mode):
                self.displayErr('SequencerMode')
                return False
            sequencer_mode_on = node_sequencer_mode.GetEntryByName('On')
            if not PySpin.IsAvailable(sequencer_mode_on) or not PySpin.IsReadable(sequencer_mode_on):
                self.displayErr('SequencerMode On')
                return False
            node_sequencer_mode.SetIntValue(sequencer_mode_on.GetValue())
            self.displayValue('Sequencer mode','enabled')

            # Validate sequencer settings
            node_sequencer_configuration_valid = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerConfigurationValid'))
            if not PySpin.IsAvailable(node_sequencer_configuration_valid) \
                    or not PySpin.IsReadable(node_sequencer_configuration_valid):
                self.displayErr('SequencerConfigurationValid')
                return False
            sequencer_configuration_valid_yes = node_sequencer_configuration_valid.GetEntryByName('Yes')
            if not PySpin.IsAvailable(sequencer_configuration_valid_yes) \
                    or not PySpin.IsReadable(sequencer_configuration_valid_yes):
                self.displayErr('SequencerConfigurationValid Yes')
                return False
            if node_sequencer_configuration_valid.GetCurrentEntry().GetValue() != \
                    sequencer_configuration_valid_yes.GetValue():
                self.displayErr('SequencerConfigurationValid valid')
                return False
            self.displayValue('Sequencer configuration', 'valid')
        except PySpin.SpinnakerException as ex:
            print('Error: {}'.format(ex))
            result = False
        return result

    def reset_sequencer(self):
        try:
            result = True
            # Turn sequencer mode back off
            node_sequencer_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerMode'))
            if not PySpin.IsAvailable(node_sequencer_mode) or not PySpin.IsWritable(node_sequencer_mode):
                self.displayErr('SequencerMode')
                return False
            sequencer_mode_off = node_sequencer_mode.GetEntryByName('Off')
            if not PySpin.IsAvailable(sequencer_mode_off) or not PySpin.IsReadable(sequencer_mode_off):
                self.displayErr('SequencerMode Off')
                return False
            node_sequencer_mode.SetIntValue(sequencer_mode_off.GetValue())
            self.displayValue('SequencerMode','Off')
            # Turn automatic exposure back on
            node_exposure_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('ExposureAuto'))
            if PySpin.IsAvailable(node_exposure_auto) and PySpin.IsWritable(node_exposure_auto):
                exposure_auto_continuous = node_exposure_auto.GetEntryByName('Continuous')
                if PySpin.IsAvailable(exposure_auto_continuous) and PySpin.IsReadable(exposure_auto_continuous):
                    node_exposure_auto.SetIntValue(exposure_auto_continuous.GetValue())
                    self.displayValue('ExposureAuto','Continuous')
        except PySpin.SpinnakerException as ex:
            print('Error: {}'.format(ex))
            result = False
        return result

    def set_single_state(self, sequence_number, width_to_set, height_to_set, exposure_time_to_set, offx_to_set, offy_to_set):
        try:
            result = True

            # 选择当前Seq序列数字
            node_sequencer_set_selector = PySpin.CIntegerPtr(self.nodemap.GetNode('SequencerSetSelector'))
            if not PySpin.IsAvailable(node_sequencer_set_selector) or not PySpin.IsWritable(node_sequencer_set_selector):
                self.displayErr('SequencerSetSelector')
                return False
            node_sequencer_set_selector.SetValue(sequence_number)
            self.displayValue('Sequencer state',format(sequence_number))
            # 设置Width
            node_width = PySpin.CIntegerPtr(self.nodemap.GetNode('Width'))
            if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
                width_inc = node_width.GetInc()
                if width_to_set % width_inc != 0:
                    width_to_set = int(width_to_set / width_inc) * width_inc
                node_width.SetValue(width_to_set)
                self.displayValue('Width',format(node_width.GetValue()))
            else:
                self.displayErr('Width')
            # 设置height
            node_height = PySpin.CIntegerPtr(self.nodemap.GetNode('Height'))
            if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
                height_inc = node_height.GetInc()
                if height_to_set % height_inc != 0:
                    height_to_set = int(height_to_set / height_inc) * height_inc
                node_height.SetValue(height_to_set)
                self.displayValue('Height',format(node_height.GetValue()))
            else:
                self.displayErr('Height')
            # 设置exposure time;
            node_exposure_time = PySpin.CFloatPtr(self.nodemap.GetNode('ExposureTime'))
            if not PySpin.IsAvailable(node_exposure_time) or not PySpin.IsWritable(node_exposure_time):
                self.displayErr('ExposureTime')
                return False
            exposure_time_max = node_exposure_time.GetMax()
            if exposure_time_to_set > exposure_time_max:
                exposure_time_to_set = exposure_time_max
            node_exposure_time.SetValue(exposure_time_to_set)
            self.displayValue('exposure time',format(node_exposure_time.GetValue()))
            # 设置Offset X;
            node_offset_x = PySpin.CIntegerPtr(self.nodemap.GetNode('OffsetX'))
            if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
                node_offset_x.SetValue(offx_to_set)
                self.displayValue('Offset X',format(node_offset_x.GetValue()))
            else:
                self.displayErr('OffsetX')
            # 设置Offset Y;
            node_offset_y = PySpin.CIntegerPtr(self.nodemap.GetNode('OffsetY'))
            if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
                node_offset_y.SetValue(offy_to_set)
                self.displayValue('Offset X',format(node_offset_y.GetValue()))
            else:
                self.displayErr('OffsetY')
            # Set the trigger type for the current state
            node_sequencer_trigger_source = PySpin.CEnumerationPtr(self.nodemap.GetNode('SequencerTriggerSource'))
            if not PySpin.IsAvailable(node_sequencer_trigger_source) or not PySpin.IsWritable(node_sequencer_trigger_source):
                self.displayErr('SequencerTriggerSource')
                return False
            sequencer_trigger_source_frame_start = node_sequencer_trigger_source.GetEntryByName('FrameStart')
            if not PySpin.IsAvailable(sequencer_trigger_source_frame_start) or \
                    not PySpin.IsReadable(sequencer_trigger_source_frame_start):
                self.displayErr('SequencerTriggerSource FrameStart')
                return False
            node_sequencer_trigger_source.SetIntValue(sequencer_trigger_source_frame_start.GetValue())
            self.displayValue('Trigger source','FrameStart')
            # 0 1 2
            final_sequence_index = self.NUM_SEQ - 1
            node_sequencer_set_next = PySpin.CIntegerPtr(self.nodemap.GetNode('SequencerSetNext'))
            if not PySpin.IsAvailable(node_sequencer_set_next) or not PySpin.IsWritable(node_sequencer_set_next):
                self.displayErr('SequencerSetNext')
                return False
            if sequence_number == final_sequence_index:
                node_sequencer_set_next.SetValue(0)
            else:
                node_sequencer_set_next.SetValue(sequence_number + 1)
            self.displayValue('Next state',format(node_sequencer_set_next.GetValue()))
            # Save current state
            node_sequencer_set_save = PySpin.CCommandPtr(self.nodemap.GetNode('SequencerSetSave'))
            if not PySpin.IsAvailable(node_sequencer_set_save) or not PySpin.IsWritable(node_sequencer_set_save):
                self.displayErr('SequencerSetSave')
                return False
            node_sequencer_set_save.Execute()
            self.displayValue('Current state','saved')
        except PySpin.SpinnakerException as ex:
            print('Error: {}'.format(ex))
            result = False
        return result

    def enable_chunk_data(self):
        try:
            result = True
            print('\n*** CONFIGURING CHUNK DATA ***\n')
            chunk_mode_active = PySpin.CBooleanPtr(
                self.nodemap.GetNode('ChunkModeActive'))
            if PySpin.IsAvailable(chunk_mode_active) and PySpin.IsWritable(chunk_mode_active):
                chunk_mode_active.SetValue(True)
            self.displayValue("Chunk mode","Active")
            chunk_selector = PySpin.CEnumerationPtr(
                self.nodemap.GetNode('ChunkSelector'))
            if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
                self.displayErr('ChunkSelector')
                return False
            entries = [PySpin.CEnumEntryPtr(
                chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]
            self.displayValue("Entries","Active")
            for chunk_selector_entry in entries:
                if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                    continue
                chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
                chunk_str = '\t {}:'.format(chunk_selector_entry.GetSymbolic())
                chunk_enable = PySpin.CBooleanPtr(self.nodemap.GetNode('ChunkEnable'))
                if not PySpin.IsAvailable(chunk_enable):
                    self.displayErr(format(chunk_str))
                    result = False
                elif chunk_enable.GetValue() is True:
                    self.displayValue(format(chunk_str),"Active")
                elif PySpin.IsWritable(chunk_enable):
                    chunk_enable.SetValue(True)
                    self.displayValue(format(chunk_str),"Active")
                else:
                    self.displayErr(format(chunk_str))
                    result = False
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
        print('\n*** CONFIGURING END ***\n')
        return result

    def disable_chunk_data(self):
        try:
            result = True
            chunk_selector = PySpin.CEnumerationPtr(
                self.nodemap.GetNode('ChunkSelector'))
            if not PySpin.IsAvailable(chunk_selector) or not PySpin.IsReadable(chunk_selector):
                self.displayErr('ChunkSelector')
                return False
            entries = [PySpin.CEnumEntryPtr(
                chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]
            self.displayValue("Chunk mode","Disabled")
            for chunk_selector_entry in entries:
                if not PySpin.IsAvailable(chunk_selector_entry) or not PySpin.IsReadable(chunk_selector_entry):
                    continue
                chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
                chunk_symbolic_form = '\t {}:'.format(
                    chunk_selector_entry.GetSymbolic())
                chunk_enable = PySpin.CBooleanPtr(self.nodemap.GetNode('ChunkEnable'))
                if not PySpin.IsAvailable(chunk_enable):
                    self.displayErr(format(chunk_symbolic_form))
                    result = False
                elif not chunk_enable.GetValue():
                    self.displayValue(format(chunk_symbolic_form),"Disabled")
                elif PySpin.IsWritable(chunk_enable):
                    chunk_enable.SetValue(False)
                    self.displayValue(format(chunk_symbolic_form),"Disabled")
                else:
                    self.displayErr(format(chunk_symbolic_form))
            chunk_mode_active = PySpin.CBooleanPtr(
                self.nodemap.GetNode('ChunkModeActive'))
            if not PySpin.IsAvailable(chunk_mode_active) or not PySpin.IsWritable(chunk_mode_active):
                self.displayErr("Chunk mode")
                return False
            chunk_mode_active.SetValue(False)
            self.displayValue("Chunk mode","Disabled")
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
        return result

    def acquire_timestamp(self):
        try:
            result = True
            chunk_data_control = PySpin.CCategoryPtr(
                MASTERNODE.GetNode('ChunkDataControl'))
            if not PySpin.IsAvailable(chunk_data_control) or not PySpin.IsReadable(chunk_data_control):
                self.displayErr(format('ChunkDataControl'))
                return False
            features = chunk_data_control.GetFeatures()
            feature = features[16]
            feature_node = PySpin.CNodePtr(feature)
            feature_display_name = '\t{}:'.format(
                feature_node.GetDisplayName())
            if not PySpin.IsAvailable(feature_node) or not PySpin.IsReadable(feature_node):
                self.displayErr(format(feature_display_name))
                result &= False
            else:
                feature_value = PySpin.CValuePtr(feature)
                self.TimeStamps.append(feature_value.ToString())
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
        return result

    def acquire_images(self):
        print('*** IMAGE ACQUISITION ***\n')
        try:
            result = True
            node_acquisition_mode = PySpin.CEnumerationPtr(
                self.nodemap.GetNode('AcquisitionMode'))
            if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
                self.displayErr('AcquisitionMode')
                return False
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
            if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(node_acquisition_mode_continuous):
                self.displayErr('AcquisitionMode')
                return False
            acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
            node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
            self.displayValue('Acquisition mode','continuous')
            self.cam.BeginAcquisition()
            for i in range(self.NUM_IMAGES):
                try:
                    image_result = self.cam.GetNextImage(self.TimeOut)
                    if image_result.IsIncomplete():
                        print('Image incomplete with image status %d...' %
                            image_result.GetImageStatus())
                    else:
                        self.acquire_timestamp()
                        if savestyle == 1:
                            self.Images.put(image_result)
                        elif savestyle == 2:
                            filename =  self.SaveImgFile + '/img/image-%d.jpg' % i
                            res = image_result.GetNDArray()
                            res = cv2.cvtColor(res,self.ColorSpace)
                            cv2.imwrite(filename, res)
                        elif savestyle == 3:
                            filename =  self.SaveImgFile + '/img/image-%d.jpg' % i
                            image_result.Save(filename)
                        elif savestyle == 4:
                            self.Images.put(image_result.GetNDArray())
                        elif savestyle == 5:
                            self.Images.put(image_result.GetData())
                        elif savestyle == 6:
                            self.Images.put(image_result)
                        image_result.Release()
                except PySpin.SpinnakerException as ex:
                    print('Error: %s' % ex)
                    result = False
            self.cam.EndAcquisition()
        except PySpin.SpinnakerException as ex:
            print('Error: %s' % ex)
            result = False
        return result

    def save_images_thread(self):
        ensure_dir(os.path.join('dataout', name_out, 'Master', 'RGB'))
        ensure_dir(os.path.join('dataout', name_out, 'Master', 'RGB_crop'))
        M = np.load(r'M_mean.npy')
        i = 0
        while i < self.NUM_IMAGES:
            res_RGB = self.Images.get()
            filename_RGB =  os.path.join('dataout', name_out, 'Master', 'RGB', '%d.png' % i)
            cv2.imwrite(filename_RGB, res_RGB)
            # #### 裁剪RGB
            # filename_RGB_crop =  os.path.join('dataout', name_out, 'Master', 'RGB_crop', '%d.png' % i)
            # res_RGB_crop = cv2.warpPerspective(res_RGB, M, (width_s, height_s), flags=cv2.INTER_LINEAR)
            # cv2.imwrite(filename_RGB_crop, res_RGB_crop)
            print(f'Saving RGB image {i}: {res_RGB.shape}')
            i += 1
        with open(os.path.join('dataout', name_out, 'Master', 'TimeStamps.txt'), "w+") as f:
            for i in range(len(self.TimeStamps)):
                timestamp = self.TimeStamps[i]
                f.write('Timestamp:{}'.format(int(timestamp)/1000000000) +
                        ' ' + '%d.jpg\n' % i)
        print('All images are saved!')




class Flir():
    def __init__(self, num, ft1,ft2,ft3):
        self.NUM = num
        self.FTime1 = ft1
        self.FTime2 = ft2
        self.FTime3 = ft3
        self.images = list()

    def run(self):
        """
        Example entry point; please see Enumeration example for more in-depth
        comments on preparing and cleaning up the system.

        :return: True if successful, False otherwise.
        :rtype: bool
        """

        # Since this application saves images in the current folder
        # we must ensure that we have permission to write to this folder.
        # If we do not have permission, fail right away.
        result = True
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()

        print('Number of cameras : %d' % num_cameras)
        if num_cameras == 0:
            cam_list.Clear()
            system.ReleaseInstance()
            print('No camera!')
            print('Done! Press Enter to exit...')
            return False

        for i, cam in enumerate(cam_list):
            slave = FLIR(cam)
            global MASTERNODE
            MASTERNODE = slave.nodemap
            slave.displayValue("从相机", "时钟源")
        if not slave.config_HDR_camera():
            return False
        if not slave.enable_chunk_data():
            return False
        if not slave.init_sequencer():
            return False
        for sequence_num in range(slave.NUM_SEQ):
            result &= slave.set_single_state(sequence_num,
                                             int(slave.Width),
                                             int(slave.Height),
                                             slave.ExposureTime[sequence_num],
                                             slave.Offx,
                                             slave.Offy)
            if not result:
                return result
        if not slave.open_sequencer():
            return False

        save_thread = Thread(target=slave.save_images_thread, args=(), daemon=True)
        save_thread.start()

        slave.acquire_images()
        print("拍完了，快断开事件相机")
        # slave.save_images()
        slave.reset_sequencer()
        if not slave.disable_chunk_data():
            return False

        # 释放内存
        slave.deinit()
        del cam
        del slave
        cam_list.Clear()
        print('\nDone!\n' + '-'*100)
        system.ReleaseInstance()
        return result



class Sign_GUI():
    
    def __init__(self, window):
        self.window = window
        self.mode = tk.StringVar()
        self.lable = 'unknow'
        self.flir = Flir(10, 5000,5000,5000)
        self.t1 = None
        self.t2 = None


    def RunFlir1(self):
        flir = 'python Eventcam_TriIn.py'
        os.system(flir)

    def RunFlir2(self):
        self.flir.images = list()
        # self.flir.run()
        self.t1 = Thread(target=self.flir.run)
        self.t1.start()
        self.t1.join()  # join() 等待线程终止，要不然一直挂起

    def SetFlirET(self):
        global exposure_time_s
        global NUM_IMAGES_S
        global timeout
        # if int(self.FlirEntryETime1.get())<int(self.FlirEntryETime2.get()) and  int(self.FlirEntryETime2.get())<int(self.FlirEntryETime3.get()):
        NUM_IMAGES_S = int(self.FlirEntryE_NUM.get())
        exposure_time_s = [int(self.FlirEntryETime3.get()), int(self.FlirEntryETime1.get()), int(self.FlirEntryETime2.get())]  # 2 0 1
        timeout = int((exposure_time_s[0] / 1000) + 1000)
        if len(self.DirEntry.get())>0:
            global  name_out
            name_out = str(self.DirEntry.get())
            self.flir.run()
        else:
            print('Enter save dir')
        # else:
        #     print('Invalid Time')

    def RunEvent1(self):
        event = 'python eventcamera_trigger_in.py'
        os.system(event)

    def RunEvent2(self):
        self.t2 = Thread(target=self.RunEvent1)
        self.t2.start()
        # 等待所有线程执行完毕
        self.t2.join()

    def Run(self):
        self.t1.start()
        self.t2.start()

        # 等待所有线程执行完毕
        self.t1.join()  # join() 等待线程终止，要不然一直挂起
        self.t2.join()



    def set_window(self):

        # Window
        self.window.title("多相机协调系统 v0.1")           				# windows name
        self.window.geometry('550x500')					# size(1080, 720), place(10, 10)
        self.window.resizable(width=True, height=True) # 设置窗口是否可以变化长/宽，False不可变，True可变，默认为True
        var = tk.StringVar()
        self.ft = tkf.Font(size = 15) 	

        

        self.canvas = tk.Canvas (self.window,width=550,height=500)
        self.canvas.create_rectangle(30,160,250,480,outline='black')
        self.canvas.pack()
        self.mode_label = tk.Label(self.window,font=('楷体',25,'bold'),text='多相机协调系统(FLIR)')
        self.mode_label.place(x = 80, y = 20, width = 400, height = 60)

        self.ETlabel1 =tk.Label(self.window,font=('楷体',10,'bold'),text='曝光时间 1')
        self.ETlabel1.place(x=60, y=175, width=80, height=15)
        self.ETlabel2 = tk.Label(self.window, font=('楷体', 10, 'bold'), text='曝光时间 2')
        self.ETlabel2.place(x=60, y=270, width=80, height=15)
        self.ETlabel3 = tk.Label(self.window, font=('楷体', 10, 'bold'), text='曝光时间 3')
        self.ETlabel3.place(x=60, y=365, width=80, height=15)
        self.FlirEntryETime1 = tk.Entry(self.window, font=('楷体',20,'bold'))
        self.FlirEntryETime1.place(x = 60, y = 190, width = 140, height = 70)
        self.FlirEntryETime1.insert(0, "3000")
        self.FlirEntryETime2 = tk.Entry(self.window, font=('楷体', 20, 'bold'))
        self.FlirEntryETime2.place(x=60, y=285, width=140, height=70)
        self.FlirEntryETime2.insert(0, "3000")
        self.FlirEntryETime3 = tk.Entry(self.window, font=('楷体', 20, 'bold'))
        self.FlirEntryETime3.place(x=60, y=380, width=140, height=70)
        self.FlirEntryETime3.insert(0, "3000")
        # self.FlirButtonETime = tk.Button(self.window, font=('楷体',15,'bold'), text = "设置Flir曝光", command=self.SetFlirET)
        # self.FlirButtonETime.place(x = 230, y = 285, width = 140, height = 70)
        self.Dirlabel3 = tk.Label(self.window, font=('楷体', 10, 'bold'), text='文件名')
        self.Dirlabel3.place(x=300, y=165, width=50, height=15)
        self.DirEntry = tk.Entry(self.window, font=('楷体', 20, 'bold'))
        self.DirEntry.place(x=300, y=180, width=140, height=40)
        self.DirEntry.insert(0, "test")

        self.DirlabelNUM = tk.Label(self.window, font=('楷体', 10, 'bold'), text='总帧数')
        self.DirlabelNUM.place(x=300, y=235, width=50, height=15)
        self.FlirEntryE_NUM = tk.Entry(self.window, font=('楷体', 20, 'bold'))
        self.FlirEntryE_NUM.place(x=300, y=250, width=140, height=40)
        self.FlirEntryE_NUM.insert(0, 20)

        
        # self.FlirTextNum = tk.Text(self.window, font=('楷体',25,'bold'))
        # self.FlirTextNum.place(x = 60, y = 190, width = 140, height = 70)

        # Button
        self.Button_Flir = tk.Button(self.window, font=('楷体',10,'bold'), text = "设置并运行Flir相机", command=self.SetFlirET)
        self.Button_Flir.place(x = 300, y = 340, width = 200, height = 50)
										
        # self.Button_Event = tk.Button(self.window, font=('楷体',25,'bold'), text = "运行Event相机", command=self.RunEvent2)#, command = self.Replay)
        # self.Button_Event.place(x = 430, y = 720, width = 250, height = 50)

        # self.Button_run = tk.Button(self.window, font=('楷体', 25, 'bold'), text="运行",
        #                               command=self.Run)  # , command = self.Replay)
        # self.Button_run.place(x=430, y=800, width=250, height=50)


            

def Run_GUI():
    GUI_window = tk.Tk()              	# 实例化出一个父窗口
    GUI = Sign_GUI(GUI_window)    
    GUI.set_window()			# 设置根窗口默认属性
    GUI_window.mainloop()          	# 父窗口进入事件循环，可以理解为保持窗口运行，否则界面不展示



def main():
    Run_GUI()


if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)