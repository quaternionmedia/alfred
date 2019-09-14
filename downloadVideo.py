from pytube import YouTube

def archive(link):
    yt = YouTube(link)
    # audio
    yt.streams.filter(adaptive=True, only_video=True).order_by('abr').last()
    # video
    yt.streams.filter(adaptive=True, only_video=True, subtype='mp4').order_by('resolution').last()
    # mux
    
