# coding=utf-8
# =============================================================================
# Copyright (c) 2001-2021 FLIR Systems, Inc. All Rights Reserved.
#
# This software is the confidential and proprietary information of FLIR
# Integrated Imaging Solutions, Inc. ("Confidential Information"). You
# shall not disclose such Confidential Information and shall use it only in
# accordance with the terms of the license agreement you entered into
# with FLIR Integrated Imaging Solutions, Inc. (FLIR).
#
# FLIR MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY OF THE
# SOFTWARE, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE, OR NON-INFRINGEMENT. FLIR SHALL NOT BE LIABLE FOR ANY DAMAGES
# SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR DISTRIBUTING
# THIS SOFTWARE OR ITS DERIVATIVES.
# =============================================================================
#
#  Exposure_QuickSpin.py shows how to customize image exposure time
#  using the QuickSpin API. QuickSpin is a subset of the Spinnaker library
#  that allows for simpler node access and control.
#
#  This example prepares the camera, sets a new exposure time, and restores
#  the camera to its default state. Ensuring custom values fall within an
#  acceptable range is also touched on. Retrieving and setting information
#  is the only portion of the example that differs from Exposure.
#
#  A much wider range of topics is covered in the full Spinnaker examples than
#  in the QuickSpin ones. There are only enough QuickSpin examples to
#  demonstrate node access and to get started with the API; please see full
#  Spinnaker examples for further or specific knowledge on a topic.

import PySpin
import sys
import time
import os

NUM_IMAGES = 50  # number of images to save

FRAMERATE = 520
EXPOSURE_TIME = 1000 # us

OFFSET_X = 0
OFFSET_Y = 0
WIDTH = 720
HEIGHT = 540

def ensure_dir(s):
    if not os.path.exists(s):
        os.makedirs(s)


def print_device_info(nodemap):
    """
    This function prints the device information of the camera from the transport
    layer; please see NodeMapInfo example for more in-depth comments on printing
    device information from the nodemap.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** DEVICE INFORMATION ***\n')

    try:
        result = True
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))

        if PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not readable.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return result


def config_camera(nodemap):
    print("\n---------- CONFIG CAMERA ----------\n")
    try:
        result = True
        """ -------------------- 设置ROI -------------------- """
        node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode('OffsetX'))
        if not PySpin.IsAvailable(node_offset_x) or not PySpin.IsWritable(node_offset_x):
            print('\nUnable to set Offset X (integer retrieval). Aborting...\n')
            return False
        node_offset_x.SetValue(OFFSET_X)
        
        node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode('OffsetY'))
        if not PySpin.IsAvailable(node_offset_y) or not PySpin.IsWritable(node_offset_y):
            print('\nUnable to set Offset Y (integer retrieval). Aborting...\n')
            return False
        node_offset_y.SetValue(OFFSET_Y)
        
        node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
        if not PySpin.IsAvailable(node_width) or not PySpin.IsWritable(node_width):
            print('\nUnable to set Width (integer retrieval). Aborting...\n')
            return False
        node_width.SetValue(WIDTH)
        
        node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
        if not PySpin.IsAvailable(node_height) or not PySpin.IsWritable(node_height):
            print('\nUnable to set Height (integer retrieval). Aborting...\n')
            return False
        node_height.SetValue(HEIGHT)

        """ -------------------- 设置帧率 -------------------- """
        node_framerate_enable = PySpin.CBooleanPtr(nodemap.GetNode('AcquisitionFrameRateEnable'))
        if not PySpin.IsAvailable(node_framerate_enable) or not PySpin.IsWritable(node_framerate_enable):
            print('\nUnable to enable Framerate (boolean retrieval). Aborting...\n')
            return False
        node_framerate_enable.SetValue(True)
            
        node_acquisition_framerate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
        if not PySpin.IsReadable(node_acquisition_framerate) or not PySpin.IsWritable(node_acquisition_framerate):
            print('\nUnable to set Framerate (float retrieval). Aborting...\n')
            return False
        node_acquisition_framerate.SetValue(FRAMERATE)

        """ -------------------- 设置曝光时间 -------------------- """
        # Turn off auto exposure
        node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
        if not PySpin.IsReadable(node_exposure_auto) or not PySpin.IsWritable(node_exposure_auto):
            print('\nUnable to set Exposure Auto (enumeration retrieval). Aborting...\n')
            return False
        entry_exposure_auto_off = node_exposure_auto.GetEntryByName('Off')
        if not PySpin.IsReadable(entry_exposure_auto_off):
            print('\nUnable to set Exposure Auto (entry retrieval). Aborting...\n')
            return False
        exposure_auto_off = entry_exposure_auto_off.GetValue()
        node_exposure_auto.SetIntValue(exposure_auto_off)

        node_exposure_mode = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureMode'))
        if not PySpin.IsReadable(node_exposure_mode) or not PySpin.IsWritable(node_exposure_mode):
            print('\nUnable to set Exposure Mode (enumeration retrieval). Aborting...\n')
            return False
        entry_exposure_mode_triggerwidth = node_exposure_mode.GetEntryByName('TriggerWidth')
        if not PySpin.IsReadable(entry_exposure_mode_triggerwidth):
            print('\nUnable to set Exposure Mode TriggerWidth (entry retrieval). Aborting...\n')
            return False
        exposure_mode_triggerwidth = entry_exposure_mode_triggerwidth.GetValue()
        node_exposure_mode.SetIntValue(exposure_mode_triggerwidth)
        
        """ -------------------- 设置增益 -------------------- """
        # Turn off auto gain
        node_gain_auto = PySpin.CEnumerationPtr(nodemap.GetNode('GainAuto'))
        if not PySpin.IsReadable(node_gain_auto) or not PySpin.IsWritable(node_gain_auto):
            print('\nUnable to set Gain Auto (enumeration retrieval). Aborting...\n')
            return False
        entry_gain_auto_off = node_gain_auto.GetEntryByName('Off')
        if not PySpin.IsReadable(entry_gain_auto_off):
            print('\nUnable to set Gain Auto (entry retrieval). Aborting...\n')
            return False
        gain_auto_off = entry_gain_auto_off.GetValue()
        node_gain_auto.SetIntValue(gain_auto_off)
        
        """ -------------------- 设置白平衡 -------------------- """
        # Turn off auto balance white
        node_balance_white_auto = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceWhiteAuto'))
        if not PySpin.IsReadable(node_balance_white_auto) or not PySpin.IsWritable(node_balance_white_auto):
            print('\nUnable to set Balance White Auto (enumeration retrieval). Aborting...\n')
            return False
        entry_balance_white_auto_off = node_balance_white_auto.GetEntryByName('Off')
        if not PySpin.IsReadable(entry_balance_white_auto_off):
            print('\nUnable to set Balance White Auto (entry retrieval). Aborting...\n')
            return False
        balance_white_auto_off = entry_balance_white_auto_off.GetValue()
        node_balance_white_auto.SetIntValue(balance_white_auto_off)
        
        """ -------------------- 设置吞吐量 -------------------- """
        node_device_link_throughput_limit = PySpin.CIntegerPtr(nodemap.GetNode('DeviceLinkThroughputLimit'))
        if not PySpin.IsReadable(node_device_link_throughput_limit) or not PySpin.IsWritable(node_device_link_throughput_limit):
            print('\nUnable to set Device Link Throughput Limit (integer retrieval). Aborting...\n')
            return False
        node_device_link_throughput_limit.SetValue(500000000)
        
        """ -------------------- 设置信号输入 -------------------- """
        node_trigger_selector = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSelector'))
        if not PySpin.IsAvailable(node_trigger_selector) or not PySpin.IsWritable(node_trigger_selector):
            print('\nUnable to set Trigger Selector (enumeration retrieval). Aborting...\n')
            return False
        entry_trigger_selector = node_trigger_selector.GetEntryByName('FrameStart')
        if not PySpin.IsAvailable(entry_trigger_selector) or not PySpin.IsReadable(entry_trigger_selector):
            print('\nUnable to enter Trigger Selector FrameStart. Aborting...\n')
            return False
        trigger_selector_framestart = entry_trigger_selector.GetValue()
        node_trigger_selector.SetIntValue(trigger_selector_framestart)
        
        '''node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if not PySpin.IsAvailable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
            print('\nUnable to set Trigger Mode (enumeration retrieval). Aborting...\n')
            return False
        entry_trigger_mode_on = node_trigger_mode.GetEntryByName('On')
        if not PySpin.IsAvailable(entry_trigger_mode_on) or not PySpin.IsReadable(entry_trigger_mode_on):
            print('\nUnable to enter Trigger Mode On. Aborting...\n')
            return False
        trigger_mode_on = entry_trigger_mode_on.GetValue()
        node_trigger_mode.SetIntValue(trigger_mode_on)'''

        node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
        if not PySpin.IsAvailable(node_trigger_source) or not PySpin.IsWritable(node_trigger_source):
            print('\nUnable to set Trigger Source (enumeration retrieval). Aborting...\n')
            return False
        entry_trigger_source_line3 = node_trigger_source.GetEntryByName('Line3')
        if not PySpin.IsAvailable(entry_trigger_source_line3) or not PySpin.IsReadable(entry_trigger_source_line3):
            print('\nUnable to enter Trigger Source Line3. Aborting...\n')
            return False
        trigger_source_line3 = entry_trigger_source_line3.GetValue()
        node_trigger_source.SetIntValue(trigger_source_line3)
        
        node_trigger_activation = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerActivation'))
        if not PySpin.IsAvailable(node_trigger_activation) or not PySpin.IsWritable(node_trigger_activation):
            print('\nUnable to set Trigger Activation (enumeration retrieval). Aborting...\n')
            return False
        entry_trigger_activation_risingedge = node_trigger_activation.GetEntryByName('RisingEdge')
        if not PySpin.IsAvailable(entry_trigger_activation_risingedge) or not PySpin.IsReadable(entry_trigger_activation_risingedge):
            print('\nUnable to enter Trigger Activation Rising Edge. Aborting...\n')
            return False
        trigger_activation_risingedge = entry_trigger_activation_risingedge.GetValue()
        node_trigger_activation.SetIntValue(trigger_activation_risingedge)

        """ -------------------- 设置数据块 -------------------- """
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))
        if not PySpin.IsWritable(chunk_mode_active):
            print('\nUnable to activate Chunk Mode (boolean retrieval). Aborting...\n')
            return False
        chunk_mode_active.SetValue(True)
        
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))
        if not PySpin.IsReadable(chunk_selector) or not PySpin.IsWritable(chunk_selector):
            print('\nUnable to retrieve Chunk Selector (enumeration retrieval). Aborting...\n')
            return False
        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]
        
        print('Enabling entries...')
        # Iterate through our list and select each entry node to enable
        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())
            chunk_str = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Enable the boolean, thus enabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_str))
                result = False
            elif chunk_enable.GetValue() is True:
                print('{} enabled'.format(chunk_str))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(True)
                print('{} enabled'.format(chunk_str))
            else:
                print('{} not writable'.format(chunk_str))

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False
    return result


def disable_chunk_data(nodemap):
    """
    This function disables each type of chunk data before disabling chunk data mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :return: True if successful, False otherwise
    :rtype: bool
    """
    try:
        result = True

        # Retrieve the selector node
        chunk_selector = PySpin.CEnumerationPtr(nodemap.GetNode('ChunkSelector'))

        if not PySpin.IsReadable(chunk_selector) or not PySpin.IsWritable(chunk_selector):
            print('Unable to retrieve chunk selector. Aborting...\n')
            return False

        # Retrieve entries
        #
        # *** NOTES ***
        # PySpin handles mass entry retrieval in a different way than the C++
        # API. Instead of taking in a NodeList_t reference, GetEntries() takes
        # no parameters and gives us a list of INodes. Since we want these INodes
        # to be of type CEnumEntryPtr, we can use a list comprehension to
        # transform all of our collected INodes into CEnumEntryPtrs at once.
        entries = [PySpin.CEnumEntryPtr(chunk_selector_entry) for chunk_selector_entry in chunk_selector.GetEntries()]

        print('Disabling entries...')

        for chunk_selector_entry in entries:
            # Go to next node if problem occurs
            if not PySpin.IsReadable(chunk_selector_entry):
                continue

            chunk_selector.SetIntValue(chunk_selector_entry.GetValue())

            chunk_symbolic_form = '\t {}:'.format(chunk_selector_entry.GetSymbolic())

            # Retrieve corresponding boolean
            chunk_enable = PySpin.CBooleanPtr(nodemap.GetNode('ChunkEnable'))

            # Disable the boolean, thus disabling the corresponding chunk data
            if not PySpin.IsAvailable(chunk_enable):
                print('{} not available'.format(chunk_symbolic_form))
                result = False
            elif not chunk_enable.GetValue():
                print('{} disabled'.format(chunk_symbolic_form))
            elif PySpin.IsWritable(chunk_enable):
                chunk_enable.SetValue(False)
                print('{} disabled'.format(chunk_symbolic_form))
            else:
                print('{} not writable'.format(chunk_symbolic_form))

        # Deactivate Chunk Mode
        chunk_mode_active = PySpin.CBooleanPtr(nodemap.GetNode('ChunkModeActive'))

        if not PySpin.IsWritable(chunk_mode_active):
            print('Unable to deactivate chunk mode. Aborting...\n')
            return False

        chunk_mode_active.SetValue(False)

        print('Chunk mode deactivated...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def reset_trigger(nodemap):
    """
    This function returns the camera to a normal state by turning off trigger mode.

    :param nodemap: Transport layer device nodemap.
    :type nodemap: INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if not PySpin.IsReadable(node_trigger_mode) or not PySpin.IsWritable(node_trigger_mode):
            print('Unable to disable trigger mode (node retrieval). Aborting...')
            return False

        node_trigger_mode_off = node_trigger_mode.GetEntryByName('Off')
        if not PySpin.IsReadable(node_trigger_mode_off):
            print('Unable to disable trigger mode (enum entry retrieval). Aborting...')
            return False

        node_trigger_mode.SetIntValue(node_trigger_mode_off.GetValue())

        print('Trigger mode disabled...')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def read_chunk_data(image):
    """
    This function displays a select amount of chunk data from the image. Unlike
    accessing chunk data via the nodemap, there is no way to loop through all
    available data.

    :param image: Image to acquire chunk data from
    :type image: Image object
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True
        chunk_data = image.GetChunkData()
        exposure_time = chunk_data.GetExposureTime()
        timestamp = chunk_data.GetTimestamp()
    
    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False
    return result, exposure_time, timestamp

def acquire_images(cam, nodemap):
    """
    This function acquires and saves 10 images from a device.
    Please see Acquisition example for more in-depth comments on acquiring images.

    :param cam: Camera to acquire images from.
    :param nodemap: Device nodemap.
    :type cam: CameraPtr
    :type nodemap: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** IMAGE ACQUISITION ***\n')
    try:
        result = True

        # Set acquisition mode to continuous
        # In order to access the node entries, they have to be casted to a pointer type (CEnumerationPtr here)
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsReadable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            print('Unable to set acquisition mode to continuous (enum retrieval). Aborting...')
            return False

        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsReadable(node_acquisition_mode_continuous):
            print('Unable to set acquisition mode to continuous (entry retrieval). Aborting...')
            return False

        # Retrieve integer value from entry node
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()

        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)

        print('Acquisition mode set to continuous...')

        #  Begin acquiring images
        cam.BeginAcquisition()

        # Retrieve, convert, and save images

        # Create ImageProcessor instance for post processing images
        processor = PySpin.ImageProcessor()
        
        # Set default image processor color processing method
        #
        # *** NOTES ***
        # By default, if no specific color processing algorithm is set, the image
        # processor will default to NEAREST_NEIGHBOR method.
        processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        
        images = list()
        timestamps = list()
        exposure_times = list()
        for i in range(NUM_IMAGES):
            try:
                # Retrieve next received image and ensure image completion
                # By default, GetNextImage will block indefinitely until an image arrives.
                # In this example, the timeout value is set to [exposure time + 1000]ms to ensure that an image has enough time to arrive under normal conditions
                image_result = cam.GetNextImage()
                
                if image_result.IsIncomplete():
                    print('Image incomplete with image status %d...' % image_result.GetImageStatus())

                else:
                    # Print image information
                    width = image_result.GetWidth()
                    height = image_result.GetHeight()
                    print('Grabbed Image %d, width = %d, height = %d' % (i, width, height))
                    
                    # Read chunk data
                    result, exposure_time, timestamp = read_chunk_data(image_result)
                    exposure_times.append(exposure_time)
                    timestamps.append(timestamp)
                    
                    # Convert image to RGB8
                    images.append(processor.Convert(image_result, PySpin.PixelFormat_RGB8))
                    
                    
                # Release image
                image_result.Release()

            except PySpin.SpinnakerException as ex:
                print('Error: %s' % ex)
                return False
        
        # End acquisition
        cam.EndAcquisition()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result, images, exposure_times, timestamps


def save_images(images, exposure_times, timestamps, path):
    print('start saving images...')
    et_txt = open(os.path.join(path, 'exposure_times.txt'), 'w')
    ts_txt = open(os.path.join(path, 'timestamps.txt'), 'w')
    for i in range(len(images)):
        et_txt.write('%s\n' % exposure_times[i])
        ts_txt.write('%s\n' % timestamps[i])
        filename = os.path.join(path, str(i).rjust(5, '0') + ".png")
        images[i].Save(filename)
    et_txt.close()
    ts_txt.close()
    return True 


def run_single_camera(cam):
    """
    This function acts as the body of the example; please see NodeMapInfo example
    for more in-depth comments on setting up cameras.

    :param cam: Camera to run on.
    :type cam: CameraPtr
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True

        # Retrieve TL device nodemap and print device information
        nodemap_tldevice = cam.GetTLDeviceNodeMap()

        result &= print_device_info(nodemap_tldevice)

        # Initialize camera
        cam.Init()

        # Retrieve GenICam nodemap
        nodemap = cam.GetNodeMap()

        # Configure camera
        if config_camera(nodemap) is False:
            return False

        # Acquire images
        result, images, exposure_times, timestamps = acquire_images(cam, nodemap)
        
        # Save image
        path = os.path.join('./', time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))
        ensure_dir(path)        
        result &= save_images(images, exposure_times, timestamps, path)
        
        # Disable chunk data
        result &= disable_chunk_data(nodemap)
        
        # Reset trigger
        result &= reset_trigger(nodemap)
        
        # Deinitialize camera
        cam.DeInit()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    return result


def main():
    """
    Example entry point; please see Enumeration example for more in-depth
    comments on preparing and cleaning up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """

    # Since this application saves images in the current folder
    # we must ensure that we have permission to write to this folder.
    # If we do not have permission, fail right away.
    try:
        test_file = open('test.txt', 'w+')
    except IOError:
        print('Unable to write to current directory. Please check permissions.')
        input('Press Enter to exit...')
        return False

    test_file.close()
    os.remove(test_file.name)

    result = True

    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Get current library version
    version = system.GetLibraryVersion()
    print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()

    num_cameras = cam_list.GetSize()

    print('Number of cameras detected: %d' % num_cameras)

    # Finish if there are no cameras
    if num_cameras == 0:
        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        input('Done! Press Enter to exit...')
        return False

    # Run example on each camera
    for i, cam in enumerate(cam_list):

        print('Running example for camera %d...' % i)

        result &= run_single_camera(cam)
        print('Camera %d example complete... \n' % i)

    # Release reference to camera
    # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
    # cleaned up when going out of scope.
    # The usage of del is preferred to assigning the variable to None.
    del cam

    # Clear camera list before releasing system
    cam_list.Clear()

    # Release system instance
    system.ReleaseInstance()

    input('Done! Press Enter to exit...')
    return result


if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
