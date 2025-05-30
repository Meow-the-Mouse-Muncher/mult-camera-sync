# gst-launch-1.0 -v spinnakersrc ! video/x-raw, width=1920, height=1080, format=GRAY8,framerate=30/1 ! nvvideoconvert ! capsfilter ! video/x-raw(memory:NVMM),format=NV12,width=1920,height=1080 \
#  ! nvv4l2h264enc maxperf-enable=true bitrate=1000000 idrinterval=30 profile=1 preset-level=1 insert-vui=true insert-sps-pps=true insert-aud=true ! video/x-h264,stream-format=byte-stream \
#  ! h264parse ! rtph264pay ! udpsink host=192.168.144.50 port=8180 sync=false

 gst-launch-1.0 spinnakersrc ! video/x-raw, width=1920, height=1080, format=RGB,framerate=30/1 \
 ! videoconvert ! nvvideoconvert ! 'video/x-raw(memory:NVMM),format=NV12,width=1920,height=1080' ! nvv4l2h264enc maxperf-enable=true bitrate=2000000 idrinterval=15 insert-vui=true insert-sps-pps=true insert-aud=true preset-level=3 profile=4 ! video/x-h264,stream-format=byte-stream \
 ! h264parse ! rtph264pay ! udpsink host=192.168.144.50 port=8180 sync=false
