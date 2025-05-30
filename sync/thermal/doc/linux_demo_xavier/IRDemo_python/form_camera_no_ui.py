from callback import *
from camera_inf import *
from datetime import datetime
import threading
import os
import cv2

class Form_Camera_NO_UI():
    def __init__(self, handle):
        self.handle = handle
        self.iplist = []
        self.sframe = []
        self.imgsize = [HEIGHT, WIDTH]
        grayTypes = c_uint16 * WIDTH * HEIGHT
        bufTypes = c_uint8 * 1024
        rgbTypes = c_uint8 * 3 * WIDTH * HEIGHT
        self.gray = grayTypes()
        self.buf = bufTypes()
        self.rgb = rgbTypes()
        self.mutex = threading.Lock()
        self.isConnect = 0

        self.ip = T_IPADDR()

        self.grabdir = './grab'
        if not os.path.exists(self.grabdir):
            os.makedirs(self.grabdir)

        self.monitorconnect = False

    def set_iplist(self, iplist):
        self.iplist = iplist

    # 此函数用于接收回调的数据，这里为了演示将接收和处理放在一起， 实际处理时，建议将耗时胡数据处理放在另外线程进行，以免阻塞回调
    def set_frame(self, frame):
        self.imgsize[0] = frame.height
        self.imgsize[1] = frame.width
        self.mutex.acquire()
        self.sframe = frame
        sdk_frame2gray(self.sframe, self.gray)
        sdk_gray2rgb(self.gray, self.rgb, self.imgsize[1], self.imgsize[0], 0, 1)
        self.mutex.release()

        # 下面只是为了演示，调用opencv显示


        temp = np.array(self.sframe.buffer, dtype=np.uint16)
        max_index = np.argmax(temp)
        x = int(max_index%self.imgsize[1])
        y = int(max_index/self.imgsize[1])
        rgb = np.array(self.rgb, dtype=np.uint8).reshape(self.imgsize[0], self.imgsize[1], 3)

        maxpt = STAT_POINT()
        maxpt.sPoint.x = x
        maxpt.sPoint.y = y
        maxpt.inputEmiss = 0.98
        maxpt.inputReflect = 25.0
        maxpt.inputDis = 2.0
        get_point_temp(self.sframe, maxpt)

        text = "{:.1f}".format(maxpt.sTemp.maxTemper)
        cross_points = [(x-8, y), (x+8, y)]
        cv2.polylines(rgb, [np.int32(cross_points)], True, (255, 0, 0), thickness=1)
        cross_points = [(x, y-8), (x, y+8)]
        cv2.polylines(rgb, [np.int32(cross_points)], True, (255, 0, 0), thickness=1)
        cv2.putText(rgb, text, (x + 16, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)  # 在图像上叠加白色文本

        cv2.imshow('video', rgb)
        cv2.waitKey(1)

    def connect(self):
        if not self.monitorconnect:
            self.monitorconnect = True
            sdk_creat_connect(self.handle, self.iplist[self.handle], glbCallBackFun[self.handle], self)
        else:
            self.monitor()

    def grabpic(self):
        curtime = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%f')[:-3]
        path = self.grabdir + '/irgrab_' + str(self.handle) + '_' + curtime + '.jpg'
        raw_path = self.grabdir + '/irgrab_' + str(self.handle) + '_' + curtime + '.raw'
        print(path)
        pathbytes = str.encode(path)
        self.mutex.acquire()
        if self.isConnect == 1:
            ret = sdk_saveframe2jpg(pathbytes, self.sframe, self.rgb)
            # 保存raw格式
            # buffer = np.array(self.sframe.buffer).reshape([self.sframe.height, self.sframe.width])
            # buffer.tofile(raw_path)
        self.mutex.release()

    def form_isConnect(self):
        if sdk_isconnect(self.handle):
            return True
        else:
            return False

    def monitor(self):
        if self.monitorconnect:
            self.isConnect = self.form_isConnect()
            if not self.isConnect:
                sdk_connect(self.handle)





