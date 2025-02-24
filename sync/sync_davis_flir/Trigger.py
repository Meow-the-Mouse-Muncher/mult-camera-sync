import time
import dv_processing as dv
from dv_processing import TriggerType
from datetime import timedelta
import cv2
import pyrealsense2 as rs
import os
import numpy as np

# DAVIS
save_root = './'
save_name = 'seq_000008'
save_path = os.path.join(save_root, save_name)
os.makedirs(save_path, exist_ok=True)
# Open any camera
print("******************************************************")
print("Recording DAVIS Data!")


capture = dv.io.CameraCapture()
print(type(capture))

# Check whether frames are available
eventsAvailable = capture.isEventStreamAvailable()
framesAvailable = capture.isFrameStreamAvailable()
imuAvailable = capture.isImuStreamAvailable()
triggersAvailable = capture.isTriggerStreamAvailable()

# Initiate a preview window
cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

# Depending on the incoming signal, enable the detection of the desired type of pattern, here we enable everything.
# Enable rising edge detection
capture.deviceConfigSet(4, 1, True)
# Enable falling edge detection
capture.deviceConfigSet(4, 2, True)
# Enable pulse detection
capture.deviceConfigSet(4, 3, True)
# Enable detector
capture.deviceConfigSet(4, 0, True)

# Disable auto-exposure, set frame exposure (here 10ms)
capture.setDavisExposureDuration(timedelta(microseconds=3000))
# Read current frame exposure duration value
duration = capture.getDavisExposureDuration()
# Set frame interval duration (here 33ms for ~30FPS)
capture.setDavisFrameInterval(timedelta(microseconds=40000))
# Read current frame interval duration value
interval = capture.getDavisFrameInterval()

pipeline = rs.pipeline()

#Create a config并配置要流​​式传输的管道
config = rs.config()
config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)

profile = pipeline.start(config)

triggers_list = []
flag_falling_edge = False
flag_rising_edge = False

try:
    # Open a file to write, will allocate streams for all available data types
    writer = dv.io.MonoCameraWriter(os.path.join(save_path, 'davis.aedat4'), capture)
    # Preview
    # while capture.isRunning():
    #     if framesAvailable:
    #         # Get Frame
    #         frame = capture.getNextFrame()
    #         # print(frame.image.shape)
    #         # Write Frame
    #         if frame is not None:
    #             cv2.imshow("Preview", frame.image)
    #             cv2.resizeWindow('Preview', 346*2, 260*2)
    #             key = cv2.waitKey(18)
    #             if key & 0xFF == ord('s'):
    #                 break

    # print("Recording will start in:")
    # for i in range(5, 0, -1):
    #     print(f"{i}...")
    #     time.sleep(1)
    print("Recording started!")

    start_time = time.time()
    # Run the loop while camera is still connected
    while capture.isRunning():
        
        # Check if 2 seconds have elapsed
        if flag_rising_edge and flag_falling_edge:
            break

        
        # # Read a batch of triggers from the camera
        # triggers = capture.getNextTriggerBatch()

        # # The method does not wait for data arrive, it returns immediately with
        # # latest available data or if no data is available, returns a `None`
        #    
        if eventsAvailable:
            # Get Events
            events = capture.getNextEventBatch()
            # print(events)
            # Write Events
            if events is not None:
                writer.writeEvents(events, streamName='events')

        if framesAvailable:
            # Get Frame
            frame = capture.getNextFrame()
            # print(frame.image.shape)
            # Write Frame
            if frame is not None:
                # print("avaliable")
                cv2.imshow("Preview", frame.image)
                cv2.resizeWindow('Preview', 346*2, 260*2)
                cv2.waitKey(1)
                writer.writeFrame(frame, streamName='frames')

        if imuAvailable:
            # Get IMU data
            imus = capture.getNextImuBatch()
            # Write IMU data
            if imus is not None:
                writer.writeImuPacket(imus, streamName='imu')

        if triggersAvailable:
            # Get trigger data
            triggers = capture.getNextTriggerBatch()
            # Write trigger data
            if triggers is not None:
                for trigger in triggers:
                    if trigger.type == TriggerType.EXTERNAL_SIGNAL_FALLING_EDGE:
                        flag_falling_edge = True
                        timestamp_falling_edge = trigger.timestamp
                        print(trigger.type)
                    if trigger.type== TriggerType.EXTERNAL_SIGNAL_RISING_EDGE:
                        flag_rising_edge = True
                        timestamp_rising_edge = trigger.timestamp
                        print(trigger.type)    
                triggers_list.append(triggers)
                writer.writeTriggerPacket(triggers, streamName='triggers')

except KeyboardInterrupt:
    print("Ending recording")
    pass
cv2.destroyAllWindows()

# Trigger Assertion
num_falling_edge_trigger = 0
num_rising_edge_trigger = 0

for triggers in triggers_list:
    for trigger in triggers:
        if trigger.type ==TriggerType.EXTERNAL_SIGNAL_FALLING_EDGE:
            num_falling_edge_trigger += 1
        if trigger.type==TriggerType.EXTERNAL_SIGNAL_RISING_EDGE:
            num_rising_edge_trigger += 1

assert num_rising_edge_trigger == 1, ["Rising Edge Error!", num_rising_edge_trigger]
assert num_falling_edge_trigger == 1, ["Falling Edge Error!", num_falling_edge_trigger]

# Create dictionary with trigger timestamps
trigger_timestamps = {
    'falling_edge': timestamp_falling_edge,
    'rising_edge': timestamp_rising_edge
}

# Save timestamps to npy file
np.save(os.path.join(save_path, 'trigger.npy'), trigger_timestamps)


print("Trigger Assertion Success!")
# print("******************************************************")

# print("******************************************************")
# print("Recording RealSense Data!")



# depth_sensor = profile.get_device().first_depth_sensor()
# depth_scale = depth_sensor.get_depth_scale()
# print("Depth Scale is: " , depth_scale)

# align_to = rs.stream.color
# align = rs.align(align_to)

# # 按照日期创建文件夹

# os.makedirs(os.path.join(save_path, "color"), exist_ok=True)
# os.makedirs(os.path.join(save_path, "depth"), exist_ok=True)

# # 保存的图片和实时的图片界面
# cv2.namedWindow("live", cv2.WINDOW_AUTOSIZE)
# cv2.namedWindow("save", cv2.WINDOW_AUTOSIZE)
# saved_color_image = None # 保存的临时图片
# saved_depth_mapped_image = None
# saved_count = 0

# # 主循环
# try:
#     while saved_count <= 10:
#         frames = pipeline.wait_for_frames()

#         aligned_frames = align.process(frames)

#         aligned_depth_frame = aligned_frames.get_depth_frame()
#         color_frame = aligned_frames.get_color_frame()

#         if not aligned_depth_frame or not color_frame:
#             continue
        
#         depth_data = np.asanyarray(aligned_depth_frame.get_data(), dtype="float16")
#         depth_image = np.asanyarray(aligned_depth_frame.get_data())
#         color_image = np.asanyarray(color_frame.get_data())
#         depth_mapped_image = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)
#         cv2.imshow("live", np.hstack((color_image, depth_mapped_image)))
#         key = cv2.waitKey(30)

#         # s 保存图片
#         if key & 0xFF == ord('s'):
#             saved_color_image = color_image
#             saved_depth_mapped_image = depth_mapped_image

#             # 彩色图片保存为png格式
#             cv2.imwrite(os.path.join((save_path), "color", "{}.png".format(saved_count)), saved_color_image)
#             # 深度信息由采集到的float16直接保存为npy格式
#             np.save(os.path.join((save_path), "depth", "{}".format(saved_count)), depth_data)
#             cv2.imwrite(os.path.join((save_path), "depth", "{}.png".format(saved_count)), depth_mapped_image)
#             saved_count+=1
#         # cv2.imshow("save", np.hstack((saved_color_image, saved_depth_mapped_image)))
#         # cv2.waitKey(2)

#         # q 退出
#         if key & 0xFF == ord('q') or key == 27:
#             cv2.destroyAllWindows()
#             break    
# finally:
#     pipeline.stop()

# print("******************************************************")
