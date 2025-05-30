import sys
import os
import sys
import numpy as np
from metavision_core.event_io.raw_reader import RawReader
from metavision_core.event_io import EventsIterator
from metavision_hal import I_TriggerIn
from metavision_core.event_io.raw_reader import initiate_device


        
if __name__ == '__main__':
    data_path = "./data"
    NUM_IMAGES = 120
    files = os.listdir(data_path)
    for file in files:
        raw_file = os.path.join(data_path,file,'event', 'event.raw')
        triggers = None
        with RawReader(str(raw_file), do_time_shifting=True) as ev_data:
            while not ev_data.is_done():
                a = ev_data.load_n_events(1000000)
            triggers = ev_data.get_ext_trigger_events()
        print(f"total triggers num = {len(triggers)} pos and neg")
        # 1 is neg , 0 is pos
        triggers = triggers[triggers['p'] == 0].copy()
        try:
            print(f"pos triggers num = {len(triggers)}")
            triggers = triggers[:NUM_IMAGES-1]
            print(f"we need pos triggers num = {len(triggers)}")
            trigger_polar, trigger_time, cam = zip(*triggers)
            trigger_polar = np.array(trigger_polar)
            trigger_time = np.array(trigger_time)
            # wirte time to a txt file
            with open(os.path.join(data_path, file,'event', 'TimeStamps.txt'), "w+") as f:
                for i in range(len(trigger_time)):
                    timestamp =trigger_time[i]
                    f.write('{}'.format(int(timestamp)) +'\n')
        except:
            print(f"no trigger signal!")
