from pytube import YouTube
from subprocess import run
from os import remove

def archive(link):
    # get video meta
    yt = YouTube(link)
    # get title #HACK should be:
    # title = yt.title
    title = yt.player_config_args.get('player_response', {}).get('videoDetails', {}).get('title')
    # audio
    yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').last()
    # video
    yt.streams.filter(adaptive=True, only_video=True, subtype='mp4').order_by('resolution').last()
    # mux
    cmd = f'ffmpeg -i {title}.mp4 -i {title}.webm -vcodec copy -acodec copy -map 0:v:0 -map 1:a:0 {title}.mkv'
    run(cmd.split(' '))
    # remove(f'{title}.mp4')
    # remove(f'{title}.webm')
