import ffmpeg
import numpy as np


def renderFromQueue(queue):
    # read from db
    # start ffmpeg
    pass


def queueInfo():
    pass


def videoInfo():
    probe = ffmpeg.probe(args.in_filename)
    video_stream = next(
        (stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None
    )
    width = int(video_stream['width'])
    height = int(video_stream['height'])


def generateThumbnail():
    thumb = (
        ffmpeg.input(in_filename, ss=time)
        .filter('scale', width, -1)
        .output(out_filename, vframes=1)
        .run()
    )


def videoToArray():
    out, _ = (
        ffmpeg.input('in.mp4')
        .output('pipe:', format='rawvideo', pix_fmt='rgb24')
        .run(capture_stdout=True)
    )
    video = np.frombuffer(out, np.uint8).reshape([-1, height, width, 3])


# def export():
