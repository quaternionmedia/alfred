#!/bin/bash
if [ -z $1 ]; then
  read -p "name of tape? " NAME
  read -p "duration? " DURATION
else
  NAME=$1
  DURATION=$2
fi

LOCATION=~/Videos
VSOURCE=/dev/video0
ASOURCE=hw:3,0

ffmpeg \
  -f alsa \
    -thread_queue_size 2048 \
    -i $ASOURCE \
  -f v4l2 \
    -itsoffset 0.1 \
    -thread_queue_size 2048 \
    -vsync 2 \
    -i $VSOURCE \
      -vcodec libx264 \
        -b:a 256k \
  -threads 16 \
  -t $DURATION \
  $LOCATION/$NAME.mp4
