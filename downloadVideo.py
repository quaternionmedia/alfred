from pytube import YouTube
from subprocess import run
from os import remove

def archive(link):
    # get video meta
    yt = YouTube(link)

    # get title #HACK should be:
    # title = yt.title
    title = yt.player_config_args.get('player_response', {}).get('videoDetails', {}).get('title')
    print(f'title: {title}')

    # audio
    a = yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').last()
    print(f'downloading audio stream {a}')
    a.download()

    # video
    v = yt.streams.filter(adaptive=True, only_video=True, subtype='mp4').order_by('resolution').last()
    print(f'downloading video stream {v}')
    v.download()

    # mux
    print('muxing!')
    cmd = f'ffmpeg -i "{title}.mp4" -i "{title}.webm" -vcodec copy -acodec copy -map 0:v:0 -map 1:a:0 "{title}.mkv"'
    print(cmd)
    run(cmd, shell=True)
    # remove(f'{title}.mp4')
    # remove(f'{title}.webm')
