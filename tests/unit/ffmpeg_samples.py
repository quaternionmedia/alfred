"""What ffmpeg prints about an input, for the probe tests to read.

Not a test module (no `test_` prefix). Real output: the 4.2 build
imageio-ffmpeg ships, describing files it made, and a current build's
(stream ids in brackets, rotation as side data only).
"""

MP4_WITH_SOUND = """\
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'av.mp4':
  Duration: 00:00:03.02, start: 0.000000, bitrate: 91 kb/s
    Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, \
320x180 [SAR 1:1 DAR 16:9], 6 kb/s, 24 fps, 24 tbr, 12288 tbn, 48 tbc (default)
    Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, mono, \
fltp, 75 kb/s (default)
At least one output file must be specified
"""

WEBM_NTSC = """\
Input #0, matroska,webm, from 'v.webm':
  Duration: 00:00:02.00, start: 0.000000, bitrate: 58 kb/s
    Stream #0:0: Video: vp9 (Profile 0), yuv420p(tv), 64x48, SAR 1:1 DAR 4:3, \
29.97 fps, 29.97 tbr, 1k tbn, 1k tbc (default)
"""

MP3 = """\
Input #0, mp3, from 'a.mp3':
  Duration: 00:00:01.54, start: 0.025057, bitrate: 65 kb/s
    Stream #0:0: Audio: mp3, 44100 Hz, mono, fltp, 64 kb/s
"""

MP3_WITH_COVER_ART = MP3 + (
    '    Stream #0:1: Video: mjpeg (Baseline), yuvj420p(pc), 500x500 '
    '[SAR 1:1 DAR 1:1], 90k tbr, 90k tbn, 90k tbc (attached pic)\n'
)

PNG = """\
Input #0, png_pipe, from 'i.png':
  Duration: N/A, bitrate: N/A
    Stream #0:0: Video: png, rgb24(pc), 40x30 [SAR 1:1 DAR 4:3], 25 tbr, \
25 tbn, 25 tbc
"""

GIF = """\
Input #0, gif, from 'g.gif':
  Duration: 00:00:01.00, start: 0.000000, bitrate: 62 kb/s
    Stream #0:0: Video: gif, bgra, 80x60 [SAR 64:64 DAR 4:3], 10 fps, 10 tbr, \
100 tbn, 100 tbc
"""

ROTATED_42 = """\
  Duration: 00:00:03.02, start: 0.000000, bitrate: 91 kb/s
    Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, \
320x180 [SAR 1:1 DAR 16:9], 6 kb/s, 24 fps, 24 tbr, 12288 tbn, 48 tbc (default)
    Metadata:
      rotate          : 270
      handler_name    : VideoHandler
    Side data:
      displaymatrix: rotation of 90.00 degrees
"""

# A current ffmpeg: stream ids in brackets, no `rotate` tag, side data only.
ROTATED_CURRENT = """\
  Duration: 00:01:02.50, start: 0.000000, bitrate: 2000 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), \
yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 1800 kb/s, \
59.94 fps, 59.94 tbr, 60k tbn (default)
      Side data:
        displaymatrix: rotation of -90.00 degrees
"""
