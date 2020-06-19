from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.editor import VideoFileClip
from otto import templates


def render(edl, filename='render.mp4'):
    clips = []
    for clip in edl:
        print('making clip', clip, type(clip))
        if clip['type'] == 'template':
            tmp = getattr(templates, clip['name'])
            print('making template', tmp )
            clips.append(
                tmp(**clip['data'])
            )
        elif clip['type'] == 'video':
            clips.append(
                VideoFileClip(clip['name'])
                .subclip(clip['inpoint'])
                .set_duration(clip['duration'])
            )
    print('made clips', clips)
    video = concatenate_videoclips(clips)
    print('made video', video)
    video.write_videofile(filename, fps=30)
