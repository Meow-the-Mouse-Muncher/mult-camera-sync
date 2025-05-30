from ctypes import *
import numpy as np

dll = CDLL("./lib/libIRSDKlib_arm64.so")

WIDTH = 640
HEIGHT = 512
MAX_CAMERA = 1

MAX_POINT = 8

# 帧结构
class Frame(Structure):
    _fields_ = [('width', c_uint16),
                ('height', c_uint16),
                ('nouse1', c_uint8 * 4),
                ('TempDiv', c_uint8),
                ('nouse2', c_uint8 * 23),
                ('buffer', c_uint16 * WIDTH * HEIGHT)]


# IP结构
class T_IPADDR(Structure):
    _fields_ = [('IPAddr', c_uint8 * 32),
                ('Reserved', c_uint8 * 32),
                ('DataPort', c_uint32),
                ('isValid', c_uint8),
                ('totalOnline', c_uint8),
                ('Index', c_uint8)]


class T_POINT(Structure):
    _fields_ = [('x', c_uint16),
                ('y', c_uint16)]


class STAT_TEMPER(Structure):
    _fields_ = [('maxTemper', c_float),
                ('minTemper', c_float),
                ('avgTemper', c_float),
                ('maxTemperPT', T_POINT),
                ('minTemperPT', T_POINT)]


# 颜色
class T_COLOR(Structure):
    _fields_ = [('r', c_uint8),
                ('g', c_uint8),
                ('b', c_uint8),
                ('a', c_uint8)]


class STAT_POINT(Structure):
    _fields_ = [('sPoint', T_POINT),
                ('sTemp', STAT_TEMPER),
                ('LableEx', c_uint32 * 32),
                ('Lable', c_uint8 * 32),
                ('inputEmiss', c_float),
                ('inputReflect', c_float),
                ('inputDis', c_float),
                ('inputOffset', c_float),
                ('Area', c_float),
                ('reserved1', c_uint8),
                ('reserved2', c_uint8),
                ('reserved3', c_uint8),
                ('reserved4', c_uint8),
                ('color', T_COLOR),
                ('sAlarm', c_uint32)]


class Frame(Structure):
    _fields_ = [('width', c_uint16),
                ('height', c_uint16),
                ('nouse1', c_uint8 * 4),
                ('TempDiv', c_uint8),
                ('nouse2', c_uint8 * 5),
                ('triggerframe', c_uint8),
                ('nouse3', c_uint8 * 5),
                ('abzcnt', c_uint32),
                ('timems', c_uint32),
                ('nouse4', c_uint8 * 4),
                ('buffer', c_uint16 * WIDTH * HEIGHT)]


# sdk初始化
def sdk_init():
    dll.IRSDK_Init()


def sdk_quit():
    dll.IRSDK_Quit()

def sdk_setIPAddrArray(ipaddr):
    dll.IRSDK_SetIPAddrArray(ipaddr)



# 连接相机
def sdk_creat_connect(handle, ipaddr, callbackfun, this):
    data = py_object(this)
    dll.IRSDK_Create(handle, ipaddr, callbackfun, None, None, data)
    dll.IRSDK_Connect(handle)
    print("the connect is success")


def sdk_stop(handle):
    dll.IRSDK_Stop(handle)


def sdk_isconnect(handle):
    isconnect = dll.IRSDK_IsConnected(handle)
    return isconnect


def sdk_connect(handle):
    dll.IRSDK_Connect(handle)


def sdk_sendcommand(handle, cmd, param):
    ret = dll.IRSDK_Command(handle, cmd, param)
    return ret


# 自动校正开关
def sdk_setcaliSw(handle, sw):
    dll.IRSDK_ParamCfg(handle, 11, c_float(sw))


# 校正
def sdk_calibration(handle):
    dll.IRSDK_Calibration(handle)


# 选择温度段
def sdk_tempseg_sel(handle, i):
    dll.IRSDK_ParamCfg(handle, 7, c_float(i))


# 转灰度
def sdk_frame2gray(frame, gray):
    dll.IRSDK_Frame2Gray(frame, gray, c_float(50), c_float(50), 0)


# 转rgb
def sdk_gray2rgb(gray, rgb, w, h, paltype, pal):
    dll.IRSDK_Gray2Rgb(gray, rgb, w, h, paltype, pal)


# 保存图像
def sdk_saveframe2jpg(path, frame, rgb):
    dll.IRSDK_SaveFrame2Jpeg(path, frame, rgb, 0, None)


# 利用sdk函数从jpeg中解析出温度数据
def rd_jpeg(filename):
    sFrame = Frame()
    i = dll.IRSDK_ReadJpeg2Frame(filename.encode("UTF-8"), byref(sFrame), 0, 0)
    if not i:
        w = sFrame.width
        h = sFrame.height
        buffer = np.array(sFrame.buffer).reshape([h, w])
        return [buffer, w, h]
    else:
        return [], [], []


# 获取点温度
def get_pt_temp(frame, x, y):
    temp_array = np.array(frame.buffer).reshape([frame.height, frame.width])
    temp = (temp_array[y, x] - 10000) / 100.0
    return temp


# 获取点温度
def get_pt_temp_fbuf(buffer, x, y):
    temp = (buffer[y, x] - 10000) / 100.0
    return temp


# 获取点温度
def get_point_temp(frame, st_point):
    dll.IRSDK_GetPointTemp(frame, byref(st_point), 0)  # 最后一个参数没用
    return

