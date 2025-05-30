import sys
import tkinter as tk
import tkinter.font as tkf
import os
import threading
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

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

stc_filter_ths = 10000  # Length of the time window for filtering (in us)
stc_cut_trail = True  # If true, after an event goes through, it removes all events until change of polarity

nameoutglob = 1

roi_x0 = int(340)
roi_y0 = int(60)
roi_x1 = int(939)
roi_y1 = int(659)


def parse_args():
    import argparse
    """Defines and parses input arguments"""

    description = "Simple viewer to stream events from an event-based device or RAW file, using " + \
        "Metavision Designer Python API."

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        '-i', '--input-raw-file', dest='input_filename', metavar='INPUT_FILENAME',
        help='Path to input RAW file. If not specified, the camera live stream is used.')
    parser.add_argument(
        '-n', '--nameout', default='1')

    live_camera_args = parser.add_argument_group('Live camera input parameters '
                                                 '(not compatible with \'--filename\' flag)')
    live_camera_args.add_argument('-s', '--serial', dest='serial', metavar='ID', default='',
                                  help='Serial ID of the camera. If not provided, the first available device will '
                                  'be opened.')
    return parser.parse_args()

def save_time(input_path_dat):
    record_dat = EventDatReader(input_path_dat)
    print(record_dat)
    events = record_dat.load_n_events(record_dat.event_count())  # load the 10 next events
    print('.................Open Txt.................')
    with open("test.txt", "w+") as f:
        for i in range(events.shape[0]):
            # print(events[i][3]/1000000.0)
            f.write('{}'.format(events[i][3]/1000000.0) +
                    ' ' + '{}'.format(events[i][0]-roi_x0-1) +
                    ' ' + '{}'.format(events[i][1]-roi_y0-1) +
                    ' ' + '{}\n'.format(events[i][2]))
        f.close()
    print('.................Close Txt.................')
    print(events)

def e_refocus(raw_path,d=1.3,width=600,height=600,nameout="test",polarity: int = -1,do_time_shifting=True):
    triggers = None
    with RawReader(str(raw_path), do_time_shifting=do_time_shifting) as ev_data:
        while not ev_data.is_done():
            a = ev_data.load_n_events(1000000)
        triggers = ev_data.get_ext_trigger_events()
    print(f"triggers num = {len(triggers)}")
    try:
        trigger_polar, trigger_time, cam = zip(*triggers)
        index = (trigger_polar == 1)
        trigger_time = trigger_time[index]
        # wirte time to a txt file
        with open(os.path.join('dataout', nameout, 'event', 'TimeStamps.txt'), "w+") as f:
            for i in range(len(trigger_time)):
                timestamp =trigger_time[i]
                f.write('{}'.format(int(timestamp)/1000000000) +'\n')
    except:
         print(f"no trigger signal!")
         exit()

    if polarity in (0, 1): 
        triggers = triggers[triggers['p'] == polarity].copy()
    else:
        triggers = triggers.copy()
    time_step = len(triggers) 
    frame_t = np.array(triggers)
    mv_iterator = EventsIterator(input_path=raw_path, delta_t=10000, start_ts=0,
                                 max_duration=1200000000)
    x=[]
    y=[]
    p=[]
    t=[]
  
    for evs in mv_iterator:
        e_x, e_y, e_p, e_t = zip(*evs)
        x.extend(list(e_x))
        y.extend(list(e_y))
        p.extend(list(e_p))
        t.extend(list(e_t))
    num_events = len(t)
    global roi_x0, roi_y0
    x=np.array(x)-roi_x0
    y=np.array(y)-roi_y0
    p=np.array(p)
    t=np.array(t)

    print(f"time interval = {(t.max() - t.min())/1e6}s")

    d = 1.32 # 目标深度
    fx = 383.547  # 相机内参
    v = 0.1775 # 导轨速度
    ref_t = t[int(0.5*num_events)]
    dt = t - ref_t
    dx = dt * v * fx / d
    event_x = x + np.round(dx)
    event_x = np.clip(event_x, 0, width-1)
    time_step = 30  
    minT = t.min()
    maxT = t.max()
    interval = (maxT - minT) / time_step

    # convert events to event tensors
    pos = np.zeros((time_step, height, width))
    neg = np.zeros((time_step, height, width))
    T,H,W = pos.shape
    pos = pos.ravel()    #变成一维
    neg = neg.ravel()    
    ind = (t / interval).astype(int)
    ind[ind == T] -= 1
    event_x = x.astype(int)-x.min().astype(int)
    event_y = y.astype(int)-y.min().astype(int)
    pos_ind = p == 1
    neg_ind = p == 0
    np.add.at(pos, event_x[pos_ind] + event_y[pos_ind]*W + ind[pos_ind]*W*H, 1)
    np.add.at(neg, event_x[neg_ind] + event_y[neg_ind]*W + ind[neg_ind]*W*H, 1)
    pos = np.reshape(pos, (T,H,W))
    neg = np.reshape(neg, (T,H,W))
    sum_pos = np.sum(pos+neg,axis=0)
    sum_pos[sum_pos>3*np.mean(sum_pos)]=np.mean(sum_pos)
    sum_pos/= np.max(sum_pos)
    cv2.imwrite(os.path.join(os.path.join('dataout', nameout, 'event'), 'test.png'), sum_pos*255)
    print("OK")



class event():
    def __init__(self,num):
        self.num = num
        self.width = 1280
        self.height = 720
    def run(self):
        """Main function"""
        args = parse_args()
        from_file = False
        global nameoutglob
        args.nameout = str(nameoutglob)
        if args.input_filename:
            # Check input arguments compatibility
            if args.serial:
                print("Error: flag --serial and --filename are not compatible.")
                return 1

            # Check provided input file exists
            if not (path.exists(args.input_filename) and path.isfile(args.input_filename)):
                print("Error: provided input path '{}' does not exist or is not a file.".format(args.input_filename))
                return 1

            # Open file
            device = DeviceDiscovery.open_raw_file(args.input_filename)
            if not device:
                print("Error: could not open file '{}'.".format(args.input_filename))
                return 1

            from_file = True
        else:
            # Open camera
            device = initiate_device(path=args.serial)
            if not device:
                print("Could not open camera. Make sure you have an event-based device plugged in")
                return 1
            # set trigger
            triggerin = device.get_i_trigger_in()
            triggerin.enable(I_TriggerIn.Channel(0))
      

        #设置存放目录
        ensure_dir(os.path.join('dataout', args.nameout, 'event'))
        outputpath = os.path.join('dataout', args.nameout, 'event', 'event.raw')

        # 访问事件流功能
        ieventstream = device.get_i_events_stream()
        print(ieventstream)
        # 裁剪图像 硬件裁剪
        roi_crop_width = 600
        global roi_x0, roi_y0, roi_x1, roi_y1
        Digital_Crop = device.get_i_digital_crop()
        Digital_Crop.set_window_region((roi_x0, roi_y0, roi_x1, roi_y1),False)
        Digital_Crop.enable(True)
        
        use_Digital_Crop = True


        # 开始录制

        if ieventstream:
            if (outputpath != ""):
                ieventstream.log_raw_data(outputpath)
        else:
            print("no events stream")

        mv_iterator = EventsIterator.from_device(device=device, max_duration=1200000000)
        # 接受事件流
        height, width = mv_iterator.get_size()  # Camera Geometry
        def stop_recording():
            # 5秒后调用停止录制的函数
            ieventstream.stop_log_raw_data()
        
        # timer = threading.Timer(1, stop_recording)
        # timer.start()
        # Window - Graphical User Interface
        with MTWindow(title="Metavision Events Viewer", width=width, height=height,
                      mode=BaseWindow.RenderMode.BGR) as window:
            def keyboard_cb(key, scancode, action, mods):
                if key == UIKeyEvent.KEY_ESCAPE or key == UIKeyEvent.KEY_Q:
                    window.set_close_flag()

            window.set_keyboard_callback(keyboard_cb)

            # Event Frame Generator
            event_frame_gen = PeriodicFrameGenerationAlgorithm(sensor_width=width, sensor_height=height, fps=50,
                                                               palette=ColorPalette.Dark)

            def on_cd_frame_cb(ts, cd_frame):
                window.show_async(cd_frame)

            event_frame_gen.set_output_callback(on_cd_frame_cb)
            if not args.input_filename:
                # trig.enable()
                print("start")
            for evs in mv_iterator:
                EventLoop.poll_and_dispatch()
                if use_Digital_Crop:
                    event_frame_gen.process_events(evs)
                if window.should_close():
                    break
        stop_recording()

        print("Finished")
        trigger = e_refocus(outputpath,d=1.3,nameout=args.nameout)
        del device
        return 0



class Sign_GUI():
    
    def __init__(self, window):
        self.window = window
        self.mode = tk.StringVar()
        self.lable = 'unknow'
        self.event = event(10)
        self.t1 = None
        self.t2 = None
    def SetEventET(self):
        if len(self.DirEntry.get()) > 0:
            global nameoutglob
            nameoutglob = str(self.DirEntry.get())
            self.event.run()
        else:
            print('Enter save dir!!')

    def set_window(self):
        # Window
        self.window.title("多相机协调系统 v0.1")           				# windows name
        self.window.geometry('350x200')					# size(1080, 720), place(10, 10)
        self.window.resizable(width=True, height=True) # 设置窗口是否可以变化长/宽，False不可变，True可变，默认为True
        var = tk.StringVar()
        self.ft = tkf.Font(size = 15)

        self.canvas = tk.Canvas (self.window,width=350,height=200)
        # self.canvas.create_rectangle(30,160,400,480,outline='black')
        # self.canvas.create_rectangle(30,530,400,850,outline='black')
        self.canvas.pack()
        self.mode_label = tk.Label(self.window,font=('楷体',15,'bold'),text='多相机协调系统(EVENT)')
        self.mode_label.place(x = 10, y = 20, width = 300, height = 60)
        self.Dirlabel3 = tk.Label(self.window, font=('楷体', 10, 'bold'), text='文件名')
        self.Dirlabel3.place(x=10, y=110, width=50, height=15)
        self.DirEntry = tk.Entry(self.window, font=('楷体', 25, 'bold'))
        self.DirEntry.place(x=10, y=130, width=140, height=40)
        self.DirEntry.insert(0, "test")
        # self.FlirTextNum = tk.Text(self.window, font=('楷体',25,'bold'))
        # self.FlirTextNum.place(x = 60, y = 190, width = 140, height = 70)

        # Button
        self.Button_Flir = tk.Button(self.window, font=('楷体',10,'bold'), text = "设置并运行Event相机", command=self.SetEventET)
        self.Button_Flir.place(x = 170, y = 120, width = 150, height = 50)

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