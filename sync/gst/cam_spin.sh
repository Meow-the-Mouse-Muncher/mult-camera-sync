gst-launch-1.0 -v spinnakersrc ! "video/x-raw, width=2448, height=2048,format=BGRx" \
! videoconvert ! nvvideoconvert ! nvv4l2h264enc maxperf-enable=true bitrate=2000000 idrinterval=15 insert-vui=true insert-sps-pps=true insert-aud=true preset-level=3 profile=4 \
! video/x-h264,stream-format=byte-stream ! h264parse ! udpsink host=192.168.144.50 port=9998 sync=false