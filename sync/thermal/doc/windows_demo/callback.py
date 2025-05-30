from camera_inf import *
from form_camera import *

form_cam = []  # 全局变量,
glbFrame = []

for i in range(0, MAX_CAMERA):
    glbFrame.append(Frame())

sizeFrame = 32+WIDTH*HEIGHT*2


def FrameProc1(frame, this):
    bytebuf = string_at(frame, sizeFrame)
    memmove(addressof(glbFrame[0]), bytebuf, sizeFrame)
    if len(form_cam) > 0:
        form_cam[0].set_frame(glbFrame[0])
    return 0


def FrameProc2(frame, this):
    bytebuf = string_at(frame, sizeFrame)
    memmove(addressof(glbFrame[1]), bytebuf, sizeFrame)
    if len(form_cam) > 0:
        form_cam[1].set_frame(glbFrame[1])
    return 0


glbCallBackFun = []
VIDEOCALLBACKFUNC = CFUNCTYPE(c_int, c_void_p, c_void_p)

for i in range(0, MAX_CAMERA):
    if i == 0:
        callbackfun1 = VIDEOCALLBACKFUNC(FrameProc1)
        glbCallBackFun.append(callbackfun1)
    if i == 1:
        callbackfun2 = VIDEOCALLBACKFUNC(FrameProc2)
        glbCallBackFun.append(callbackfun2)

