"""How a render's `quality` becomes encoder settings.

Clients used to choose the encoding by sending `ffmpeg_params` and `bitrate`,
and both went onto ffmpeg's command line unexamined -- arbitrary options to a
program that can read and write files, open network connections and spend as
much CPU as it is told to. The control-plane record names `ffmpeg_params` as
an accepted leak that must not widen; this closes it instead.

A client now picks a named preset (`draft`, `standard` or `high`; `standard` by
default), and the server maps it onto `renderMultitrack`'s existing parameters
(contract C5). The client says how good; the server says how.

Quality comes from x264's constant-rate factor rather than a bitrate: it holds
quality steady across easy and difficult footage, which a fixed bitrate does
not, and it is what the encoder recommends for files that are not being
streamed at a fixed rate.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Preset:
    name: str
    # Appended to moviepy's own ffmpeg options, which come first -- so the
    # `-preset` here overrides moviepy's default `-preset medium`.
    ffmpeg_params: Tuple[str, ...]
    audio_bitrate: str
    # A fixed video bitrate, as one string ('5000k'). None leaves the rate to
    # the constant-rate factor above.
    bitrate: Optional[str] = None

    def encoder_args(self) -> dict:
        """Keyword arguments for `otto.render.renderMultitrack`."""
        return dict(
            bitrate=self.bitrate,
            audio_bitrate=self.audio_bitrate,
            ffmpeg_params=list(self.ffmpeg_params),
        )


PRESETS = {
    preset.name: preset
    for preset in (
        Preset('draft', ('-preset', 'ultrafast', '-crf', '30'), audio_bitrate='128k'),
        Preset('standard', ('-preset', 'medium', '-crf', '23'), audio_bitrate='192k'),
        Preset('high', ('-preset', 'slow', '-crf', '18'), audio_bitrate='320k'),
    )
}

DEFAULT_QUALITY = 'standard'

QUALITIES = tuple(PRESETS)


class UnknownQuality(ValueError):
    """A quality that is not one of the presets."""


def preset_for(quality, strict=True) -> Preset:
    """The preset a `quality` names; the default for None or empty.

    `strict=False` falls back to the default instead of raising. That is for
    renders stored before presets existed -- the form flow saved `web` and
    `TV` -- which should re-render rather than become unrenderable.
    """
    if quality is None or quality == '':
        return PRESETS[DEFAULT_QUALITY]
    if quality in PRESETS:
        return PRESETS[quality]
    if strict:
        raise UnknownQuality(
            f'quality must be one of {", ".join(QUALITIES)}, not {quality!r}'
        )
    return PRESETS[DEFAULT_QUALITY]
