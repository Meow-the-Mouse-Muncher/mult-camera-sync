import PySpin
import sys
import time
import os
import sys
import tkinter as tk
import tkinter.font as tkf
from threading import Thread
import pigpio
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
from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, ColorPalette
from metavision_sdk_ui import EventLoop, BaseWindow, MTWindow, UIAction, UIKeyEvent
import argparse
import time
import os


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Metavision RAW file Recorder sample.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-o', '--output-dir', default="./event_data", help="Directory where to create RAW file with recorded event data")
    args = parser.parse_args()
    return args


def main():
    """ Main """
    args = parse_args()

    # HAL Device on live camera
    device = initiate_device("")

    # Start the recording
    if device.get_i_events_stream():
        log_path = "recording_" + time.strftime("%y%m%d_%H%M%S", time.localtime()) + ".raw"
        if args.output_dir != "":
            os.makedirs(args.output_dir,exist_ok=True)
            log_path = os.path.join(args.output_dir, log_path)
        print(f'Recording to {log_path}')
        device.get_i_events_stream().log_raw_data(log_path)

    # Events iterator on Device
    mv_iterator = EventsIterator.from_device(device=device)
    height, width = mv_iterator.get_size()  # Camera Geometry

    # Event Frame Generator
    event_frame_gen = PeriodicFrameGenerationAlgorithm(sensor_width=width, sensor_height=height, fps=25,
                                                        palette=ColorPalette.Dark)
    i=0
    # Process events
    for evs in mv_iterator:
        # Dispatch system events to the window
        EventLoop.poll_and_dispatch()
        event_frame_gen.process_events(evs)

        # if window.should_close():
        #     # Stop the recording
        i+=1
        print(i)
        if i>20:
            device.get_i_events_stream().stop_log_raw_data()
            break
        


if __name__ == "__main__":
    main()
