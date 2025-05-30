from callback import *
from ui_camera import Ui_Form_Camera
from camera_inf import *
from PyQt5.QtWidgets import *
from PyQt5 import QtCore
from datetime import datetime
import threading
import os


class Form_Camera(QWidget, Ui_Form_Camera):
    def __init__(self, handle):
        super(Form_Camera, self).__init__()
        self.setupUi(self)
        self.handle = handle

        self.toolButton_connect.clicked.connect(self.connect)
        self.toolButton_pic.clicked.connect(self.grabpic)

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
        self.interval = 1000   # 触发的时间间隔为1秒。
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.monitor)  # 每隔一段时间就会触发一次函数。
        timer.start(self.interval)

    def set_iplist(self, iplist):
        self.iplist = iplist

    def set_ip2combox(self, ip):
        self.comboBox_ip.setEditText(ip)

    def set_frame(self, frame):
        self.imgsize[0] = frame.height
        self.imgsize[1] = frame.width
        self.mutex.acquire()
        self.sframe = frame
        sdk_frame2gray(self.sframe, self.gray)
        sdk_gray2rgb(self.gray, self.rgb, self.imgsize[1], self.imgsize[0], 0, 1)
        self.mutex.release()
        self.label.show_img(self.rgb, frame, self.imgsize)

    def clear_ip(self):
        self.comboBox_ip.clear()

    def add_ip(self, ip):
        ip_str = (ip.split('\0'))[0]
        self.comboBox_ip.addItem(ip_str)

    def connect(self):
        self.monitorconnect = True
        index = self.comboBox_ip.currentIndex()
        if index >= 0:
            sdk_creat_connect(self.handle, self.iplist[index], glbCallBackFun[self.handle], self)
        else:  # 手动输入
            str_ip = self.comboBox_ip.currentText()
            str_iplist = str_ip.split('.')
            port = 30005 + 100 * int(str_iplist[3])
            str_ip_as_bytes = str.encode(str_ip)

            for i in range(0, len(str_ip_as_bytes)):
                self.ip.IPAddr[i] = str_ip_as_bytes[i]
            self.ip.DataPort = port
            self.ip.isValid = 1
            sdk_creat_connect(self.handle, self.ip, glbCallBackFun[self.handle], self)

    def grabpic(self):
        curtime = datetime.now().strftime('%Y-%m-%d %H.%M.%S.%f')[:-3]
        path = self.grabdir + '/irgrab_' + str(self.handle) + '_' + curtime + '.jpg'
        raw_path = self.grabdir + '/irgrab_' + str(self.handle) + '_' + curtime + '.raw'
        print(path)
        pathbytes = str.encode(path)
        self.mutex.acquire()
        if self.isConnect == 1:
            ret = sdk_saveframe2jpg(pathbytes, self.sframe, self.rgb)
            buffer = np.array(self.sframe.buffer).reshape([self.sframe.height, self.sframe.width])
            buffer.tofile(raw_path)
        self.mutex.release()

    def form_isConnect(self):
        if sdk_isconnect(self.handle):
            return True
        else:
            return False

    def monitor(self):
        if self.monitorconnect:
            self.isConnect = self.form_isConnect()
            print(self.isConnect)
            if not self.isConnect:
                sdk_connect(self.handle)





