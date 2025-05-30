from ui_mainwindow import Ui_MainWindow
from form_camera import Form_Camera
from callback import *
from PyQt5 import QtCore
from PyQt5.QtWidgets import *
import sys


class IRDemo(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(IRDemo, self).__init__()
        self.setupUi(self)

        self.setWindowTitle("IRDemo")
        for i in range(0, MAX_CAMERA):
            form_cam.append(Form_Camera(i))
            self.horizontalLayout.addWidget(form_cam[i])

        # ip结构体
        self.iplist = []
        self.ipaddr_array = []  #返回的结构指针
        self.ipaddr = []
        for i in range(0, 32):
            ip_addr = T_IPADDR()
            self.ipaddr.append(ip_addr)
        self.ip_addr_array = (T_IPADDR * 32)(*self.ipaddr)

        self.interval = 1000   # 触发的时间间隔为1秒。
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.monitor)  # 每隔一段时间就会触发一次函数。
        timer.start(self.interval)

        self.lasttotalIp = 0
        self.totalIp = 0
        sdk_init()
        sdk_setIPAddrArray(self.ip_addr_array)

        # 状态
        self.label1 = QLabel()
        self.label1.setText('v1.3.0')
        self.statusBar().addPermanentWidget(self.label1)

        self.action_calibration.triggered.connect(self.set_calibration)
        self.action_tempSelLow.triggered.connect(lambda: self.set_tempseg(0))
        self.action_tempSelMid.triggered.connect(lambda: self.set_tempseg(1))
        self.action_tempSelHigh.triggered.connect(lambda: self.set_tempseg(2))
        self.menuBar.setHidden(True)

    def AddIp2Item(self):
        self.totalIp = self.iplist[0].totalOnline
        if self.totalIp != self.lasttotalIp:
            for i in range(0, MAX_CAMERA):
                form_cam[i].clear_ip()
                form_cam[i].set_iplist(self.iplist)
                for j in range(0, self.totalIp):
                    addr = np.frombuffer(self.iplist[j].IPAddr, dtype=np.uint8).tobytes()
                    ip_str = addr.decode('utf-8')
                    form_cam[i].add_ip(ip_str)
            self.lasttotalIp = self.totalIp

    def monitor(self):
        # sdk_inqure_ip(self.ip_addr_array, self.interval)

        # if not isconnect:
        #     sdk_connect(0)
        self.ipaddr_array_to_iplist()
        self.AddIp2Item()


    #将返回的指针转成结构体
    def ipaddr_array_to_iplist(self):
        self.ipaddr_array = np.frombuffer(self.ip_addr_array, dtype=T_IPADDR, count=32)
        self.iplist.clear()
        for i in range(0, 32):
            ip = T_IPADDR()
            ip.IPAddr = tuple(self.ipaddr_array[i]['IPAddr'])
            ip.Reserved = tuple(self.ipaddr_array[i]['Reserved'])
            ip.DataPort = self.ipaddr_array[i]['DataPort']
            ip.isValid = self.ipaddr_array[i]['isValid']
            ip.totalOnline = self.ipaddr_array[i]['totalOnline']
            ip.Index = self.ipaddr_array[i]['Index']
            self.iplist.append(ip)

    def set_calibration(self):
        for i in range(0, MAX_CAMERA):
            sdk_calibration(i)

    def set_tempseg(self, index):
        for i in range(0, MAX_CAMERA):
            sdk_tempseg_sel(i, index)

    def closeEvent(self, event):
        for i in range(0, MAX_CAMERA):
            sdk_stop(i)
        sdk_quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = IRDemo()
    ui.show()
    sys.exit(app.exec_())


