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
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io.py_reader import EventDatReader
from os import path
import metavision_hal
from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, ColorPalette, RoiFilterAlgorithm
from metavision_core.event_io import EventsIterator, DatWriter
from metavision_hal import DeviceDiscovery
# , DeviceRoi
from metavision_hal import I_TriggerIn,I_DigitalCrop
from metavision_core.event_io.raw_reader import initiate_device
# from metavision_designer_engine import Controller, KeyboardEvent
# from metavision_designer_core import HalDeviceInterface, CdProducer, FrameGenerator, ImageDisplayCV
from metavision_core.event_io import LiveReplayEventsIterator, is_live_camera
from metavision_sdk_base import EventCDBuffer
from metavision_sdk_cv import ActivityNoiseFilterAlgorithm, TrailFilterAlgorithm, SpatioTemporalContrastAlgorithm
from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, PolarityFilterAlgorithm, RoiFilterAlgorithm
from metavision_sdk_ui import EventLoop, BaseWindow, MTWindow, UIAction, UIKeyEvent
# prophesee camera set
stc_filter_ths = 10000  # Length of the time window for filtering (in us)
stc_cut_trail = True  # If true, after an event goes through, it removes all events until change of polarity

nameoutglob = 1

roi_x0 = int(340)
roi_y0 = int(60)
roi_x1 = int(939)
roi_y1 = int(659)


class event():
    def __init__(self,num,path):
        self.num = num
        self.width = 1280
        self.height = 720
        self.path = path
        self.outputpath = os.path.join(path, 'event', 'event.raw')
        self.ieventstream = None
        self.device = None
    def prophesee_tirgger_found(self,polarity: int = 1,do_time_shifting=True):
        triggers = None
        with RawReader(str(self.outputpath), do_time_shifting=do_time_shifting) as ev_data:
            while not ev_data.is_done():
                a = ev_data.load_n_events(1000000)
            triggers = ev_data.get_ext_trigger_events()
        print(f"triggers num = {len(triggers)}")
        if polarity in (0, 1): 
            triggers = triggers[triggers['p'] == polarity].copy()
        else:
            triggers = triggers.copy()
        try:
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
        roi_crop_width = 600
        global roi_x0, roi_y0, roi_x1, roi_y1
        Digital_Crop = self.device.get_i_digital_crop()
        Digital_Crop.set_window_region((roi_x0, roi_y0, roi_x1, roi_y1),False)
        Digital_Crop.enable(True)
        
        use_Digital_Crop = True
        
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
        a=0
        for evs in mv_iterator:
            a+=1
            if a>100:
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



if __name__ == '__main__':
    ## config prophesee camera
    path = os.path.join('./', time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))
    ensure_dir(path) 
    prophesee_cam = event(0,path)
    prophesee_cam.config_prophesee()
    prophesee_cam.start_recording()
    prophesee_cam.stop_recording()
    prophesee_cam.prophesee_tirgger_found()