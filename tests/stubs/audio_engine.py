"""A deterministic audio engine for the test stack: joe's media API, no model.

`test_e2e.yml` runs this from the api image as the stack's audio engine, so
the browser suite can caption a real timeline through the real worker -- and
through vox -- without a speech model, a download or a running joe. It answers
the routes joe's media API answers (`POST /api/media`, `.../transcribe`,
`.../analyze`, `GET /api/media/capabilities`, `DELETE /api/media/{id}`,
`GET /api/health`) in joe's shapes.

What it "hears" comes from the sound it is sent, not from a script it plays
back regardless: every stretch of sound louder than a whisper becomes one
segment, timed where the sound is, saying the next line of `SCRIPT`, its
words spread evenly across it. A timeline that puts a burst of tone at 1.5 s
gets a caption at 1.5 s; one that moves it gets the caption moved. Analysis
is measured from the same sound.

`GET /stub/uploads` lists what was uploaded -- type, rate, channels, length --
so a test can check what alfred sent. With `--fixture-dir`, it also writes
`e2e-speech.wav` there at startup: four seconds holding two bursts of tone
(0.5-1.5 s and 2.0-3.2 s), for a timeline to put somewhere.

    python tests/stubs/audio_engine.py --port 8010 [--fixture-dir videos]
"""

import argparse
import io
import math
import os
import struct
import subprocess
import tempfile
import uuid
import wave
from array import array

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

RATE = 16000
FRAME = RATE // 50  # 20 ms
# Louder than this, as a 16-bit RMS, is sound (about -36 dBFS).
THRESHOLD = 500
# Shorter gaps than this join two stretches of sound into one.
GAP = 0.2
# Shorter stretches than this are not speech.
SHORTEST = 0.1
MAX_BYTES = 100 * 1024 * 1024
# What joe's capabilities say besides: the longest media it takes, and how
# long an upload is kept. The stub enforces neither; it says them.
MAX_SECONDS = 4 * 3600
TTL_SECONDS = 3600

SCRIPT = (
    'the first thing said',
    'and then a second line',
    'a third and final remark',
)

FEATURES = ('tempo', 'beats', 'onsets', 'loudness', 'silence', 'peaks')
TYPES = {
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
    'audio/wave': 'wav',
    'audio/mpeg': 'mp3',
    'audio/ogg': 'ogg',
    'audio/flac': 'flac',
    'audio/mp4': 'm4a',
    'audio/aac': 'aac',
    'audio/webm': 'webm',
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
    'video/webm': 'webm',
    'video/x-matroska': 'mkv',
}

FIXTURE = 'e2e-speech.wav'
FIXTURE_BURSTS = ((0.5, 1.5, 440.0), (2.0, 3.2, 660.0))
FIXTURE_SECONDS = 4.0

app = FastAPI(title='Stub audio engine')
media = {}
uploads = []


def ffmpeg():
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


class NoSound(Exception):
    pass


def decode(body: bytes, extension: str) -> array:
    """The sound in `body` as 16 kHz mono 16-bit samples. NoSound, in joe's
    words, when there is none to have."""
    with tempfile.TemporaryDirectory() as folder:
        source = os.path.join(folder, f'upload.{extension}')
        with open(source, 'wb') as handle:
            handle.write(body)
        # What streams it has: a video with none of sound is refused as such.
        described = subprocess.run(
            [ffmpeg(), '-nostdin', '-hide_banner', '-i', source],
            capture_output=True,
        ).stderr.decode('utf-8', 'replace')
        if 'Stream #' in described and 'Audio:' not in described:
            raise NoSound('this media has no audio stream')
        result = subprocess.run(
            [
                ffmpeg(),
                '-nostdin',
                '-v',
                'error',
                '-i',
                source,
                '-vn',
                '-ac',
                '1',
                '-ar',
                str(RATE),
                '-f',
                's16le',
                'pipe:1',
            ],
            capture_output=True,
        )
    if result.returncode != 0:
        said = result.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise NoSound(
            'this media has no audio ffmpeg can decode: ' + (said[-1] if said else '')
        )
    samples = array('h')
    samples.frombytes(result.stdout[: len(result.stdout) // 2 * 2])
    if not samples:
        raise NoSound('this media has no audio stream')
    return samples


def described(body: bytes, content_type: str) -> dict:
    """What a WAV upload's header says; the type alone for anything else."""
    seen = {'content_type': content_type, 'bytes': len(body)}
    if content_type.endswith(('wav', 'wave')):
        try:
            with wave.open(io.BytesIO(body)) as reader:
                seen.update(
                    sample_rate=reader.getframerate(),
                    channels=reader.getnchannels(),
                    sample_width=reader.getsampwidth(),
                    duration=round(reader.getnframes() / reader.getframerate(), 3),
                )
        except (wave.Error, EOFError, ZeroDivisionError):
            seen['unreadable'] = True
    return seen


def loudness(samples) -> list:
    """Each 20 ms frame's RMS."""
    out = []
    for start in range(0, len(samples), FRAME):
        frame = samples[start : start + FRAME]
        out.append(math.sqrt(sum(s * s for s in frame) / len(frame)) if frame else 0.0)
    return out


def stretches(samples, threshold=THRESHOLD, gap=GAP) -> list:
    """(start, end) in seconds of each stretch of sound: louder than
    `threshold` (a 16-bit RMS), with gaps shorter than `gap` seconds joined."""
    seconds = FRAME / RATE
    runs, start = [], None
    for index, level in enumerate(loudness(samples) + [0.0]):
        if level > threshold and start is None:
            start = index
        elif level <= threshold and start is not None:
            runs.append([start * seconds, index * seconds])
            start = None
    joined = []
    for run in runs:
        if joined and run[0] - joined[-1][1] < gap:
            joined[-1][1] = run[1]
        else:
            joined.append(run)
    return [(round(a, 3), round(b, 3)) for a, b in joined if b - a >= SHORTEST]


def heard(samples, words=True) -> list:
    segments = []
    for number, (start, end) in enumerate(stretches(samples)):
        line = SCRIPT[number % len(SCRIPT)]
        said = line.split()
        step = (end - start) / len(said)
        # joe trims a segment's text; its words keep whisper's leading space,
        # so they join back into it.
        segment = {'start': start, 'end': end, 'text': line}
        if words:
            segment['words'] = [
                {
                    'start': round(start + k * step, 3),
                    'end': round(start + (k + 1) * step, 3),
                    'word': f' {word}',
                    'probability': 0.9,
                }
                for k, word in enumerate(said)
            ]
        segments.append(segment)
    return segments


GONE = 'no such media: it was never uploaded here, has expired, or was deleted'


def known(media_id: str) -> array:
    if media_id not in media:
        raise HTTPException(status_code=404, detail=GONE)
    return media[media_id]


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/media/capabilities')
def capabilities():
    return {
        'formats': sorted(TYPES),
        'features': list(FEATURES),
        'speech_model': 'stub',
        'word_timestamps': True,
        'max_bytes': MAX_BYTES,
        'max_seconds': MAX_SECONDS,
        'ttl_seconds': TTL_SECONDS,
    }


@app.post('/api/media', status_code=201)
async def upload(request: Request):
    body = await request.body()
    if len(body) > MAX_BYTES:
        raise HTTPException(status_code=413, detail='too large')
    content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    extension = TYPES.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=415, detail=f'unsupported type {content_type!r}'
        )
    uploads.append(described(body, content_type))
    try:
        samples = decode(body, extension)
    except NoSound as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    media_id = uuid.uuid4().hex
    media[media_id] = samples
    return {
        'media_id': media_id,
        'duration': round(len(samples) / RATE, 3),
        'sample_rate': RATE,
        'channels': 1,
        'has_audio': True,
    }


@app.post('/api/media/{media_id}/transcribe')
def transcribe(media_id: str, language: str = None, words: bool = True):
    samples = known(media_id)
    segments = heard(samples, words=words)
    if not words:
        for segment in segments:
            segment['words'] = []
    return {
        'text': ' '.join(s['text'] for s in segments),
        'language': language or 'en',
        'segments': segments,
        'info': {
            'model': 'stub',
            'language': language or None,
            'words': words,
            'duration': round(len(samples) / RATE, 3),
            'avg_logprob': -0.3 if segments else None,
            'no_speech_prob': 0.01 if segments else None,
            'compression_ratio': 1.0 if segments else None,
        },
    }


@app.post('/api/media/{media_id}/analyze')
def analyze(
    media_id: str,
    features: str = ','.join(FEATURES),
    peaks_rate: float = 50,
    silence_db: float = -40,
    silence_min: float = 0.5,
):
    """joe's analysis, measured from the sound. `peaks_rate` is envelope
    values a second; `silence_db`, how quiet silence is (dBFS); `silence_min`,
    the shortest silence reported, in seconds."""
    samples = known(media_id)
    wanted = [f for f in features.split(',') if f]
    unknown = [f for f in wanted if f not in FEATURES]
    if unknown:
        raise HTTPException(status_code=422, detail=f'unknown features {unknown}')
    if not 1 <= peaks_rate <= 1000 or not 0 < silence_min <= 3600:
        raise HTTPException(
            status_code=422, detail='peaks_rate or silence_min out of bounds'
        )
    if not -120 <= silence_db <= 0:
        raise HTTPException(status_code=422, detail='silence_db out of bounds')
    duration = round(len(samples) / RATE, 3)
    threshold = 32768 * 10 ** (silence_db / 20)
    sound = stretches(samples, threshold=threshold)
    answer = {'duration': duration}
    if 'tempo' in wanted:
        answer['tempo'] = 120.0
    if 'beats' in wanted:
        answer['beats'] = [round(k * 0.5, 3) for k in range(int(duration / 0.5) + 1)]
    if 'onsets' in wanted:
        answer['onsets'] = [start for start, _ in sound]
    if 'loudness' in wanted:
        peak = max((abs(s) for s in samples), default=0)
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))

        def db(level):
            return round(20 * math.log10(level / 32768), 2) if level else None

        answer['loudness'] = {'rms_db': db(rms), 'peak_db': db(peak), 'lufs': None}
    if 'silence' in wanted:
        edges = [0.0] + [t for pair in sound for t in pair] + [duration]
        answer['silences'] = [
            {'start': a, 'end': b}
            for a, b in zip(edges[::2], edges[1::2], strict=True)
            if b - a >= silence_min
        ]
    if 'peaks' in wanted:
        step = max(1, int(RATE / peaks_rate))
        answer['peaks'] = {
            'rate': peaks_rate,
            'values': [
                round(
                    max((abs(s) for s in samples[i : i + step]), default=0) / 32768, 3
                )
                for i in range(0, len(samples), step)
            ],
        }
    return answer


@app.delete('/api/media/{media_id}', status_code=204)
def forget(media_id: str):
    known(media_id)
    del media[media_id]
    return Response(status_code=204)


@app.get('/stub/uploads')
def seen():
    return JSONResponse(uploads)


def write_fixture(folder: str) -> str:
    """Four seconds of 44.1 kHz mono: silence, two bursts of tone, silence."""
    rate = 44100
    frames = bytearray()
    for index in range(int(FIXTURE_SECONDS * rate)):
        t = index / rate
        value = 0.0
        for start, end, pitch in FIXTURE_BURSTS:
            if start <= t < end:
                value = 0.5 * math.sin(2 * math.pi * pitch * t)
        frames += struct.pack('<h', int(value * 32767))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, FIXTURE)
    with wave.open(path, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(bytes(frames))
    return path


if __name__ == '__main__':
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--fixture-dir')
    options = parser.parse_args()
    if options.fixture_dir:
        print('wrote', write_fixture(options.fixture_dir), flush=True)
    uvicorn.run(app, host=options.host, port=options.port)
