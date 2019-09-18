from pytube import YouTube
from subprocess import run
from os import remove
from srt import clean_up
import logging

logging.basicConfig(level=logging.INFO)


def archive(link):
    # get video meta
    yt = YouTube(link)
    vtype = None
    # get title #HACK should be:
    # title = yt.title
    title = yt.player_config_args.get('player_response', {}).get('videoDetails', {}).get('title')
    logging.info(f'title: {title}')

    # video
    v = yt.streams.filter(adaptive=True, only_video=True, subtype='mp4').order_by('resolution').last()
    logging.info(f'downloading video stream {v}')
    try:
        v.download(filename_prefix='v_')
        logging.info('download success!')
        vtype = 'mp4'
    except Exception as e:
        try:
            logging.error(f'download failed with {e}')
            v = yt.streams.filter(adaptive=True, only_video=True,subtype='webm').order_by('resolution').last()
            logging.info(f'downloading alternate stream {v}')
            v.download(filename_prefix='v_')
            logging.info('secondary download success!')
            vtype = 'webm'
        except Exception as e:
            logging.error(f'hmmm.... downloading failed again. Reverting to progressive download')
            v = yt.streams.filter(progressive=True).order_by('resolution').last()
            logging.info(f'downloading terciary stream {v}')
            v.download(filename_prefix='v_')
            logging.info('terciary download success!')
            vtype = 'mp4'

    # audio
    a = yt.streams.filter(adaptive=True, only_audio=True).order_by('abr').last()
    logging.info(f'downloading audio stream {a}')
    a.download(filename_prefix='a_')
    # mux
    logging.info('muxing!')
    cmd = f'''ffmpeg -i 'v_{title}.{vtype}' -i 'a_{title}.webm' -vcodec copy -acodec copy -map 0:v:0 -map 1:a:0 '{title}.mkv' '''
    logging.info(f'running {cmd}')
    run(cmd, shell=True)
    logging.info('removing files')
    remove(f'v_{title}.{vtype}')
    remove(f'a_{title}.webm')
    logging.info(f'successfully downloaded {title}')


def getCaptions(link):
    yt = YouTube(link)

    caption = yt.captions.get_by_language_code('en')
    if caption:
        caption = caption.generate_srt_captions()
        # with open('cap.txt', 'w') as f:
        #     f.write(caption)
        caption = clean_up(caption.split('\n'))
        caption = [c+' ' for c in caption]
        logging.info('getCaption success!')
        return ''.join(caption)
    else:
        logging.error('no captions found :(')
