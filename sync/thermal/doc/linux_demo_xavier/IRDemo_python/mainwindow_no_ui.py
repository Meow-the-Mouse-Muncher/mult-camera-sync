from form_camera_no_ui import Form_Camera_NO_UI
from callback import *
import sys
#
import threading
import time


class IRDemo():
    def __init__(self):
        for i in range(0, MAX_CAMERA):
            form_cam.append(Form_Camera_NO_UI(i))

        # ip结构体
        self.iplist = []
        self.ipaddr_array = []  #返回的结构指针
        self.ipaddr = []
        for i in range(0, 32):
            ip_addr = T_IPADDR()
            self.ipaddr.append(ip_addr)
        self.ip_addr_array = (T_IPADDR * 32)(*self.ipaddr)

        self.totalIp = 0
        sdk_init()
        sdk_setIPAddrArray(self.ip_addr_array)

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


if __name__ == "__main__":
    demo = IRDemo()
    while True:  # 监控ip在线
        demo.ipaddr_array_to_iplist()
        if len(demo.iplist) > 0:
            if demo.iplist[0].totalOnline > 0:  # 如果有ip在线，自动连接第一个ip
                demo.totalIp = demo.iplist[0].totalOnline
                addr = np.frombuffer(demo.iplist[0].IPAddr, dtype=np.uint8).tobytes()
                ip_str = addr.decode('utf-8')
                print(ip_str + "在线")
                form_cam[0].set_iplist(demo.iplist)
                form_cam[0].connect()
        time.sleep(1)


