"""How a render's `quality` becomes an encoding.

Clients used to choose the encoding by sending `ffmpeg_params` and `bitrate`,
and both went onto ffmpeg's command line unexamined -- arbitrary options to a
program that can read and write files, open network connections and spend as
much CPU as it is told to. The control-plane record names `ffmpeg_params` as
an accepted leak that must not widen; this closes it instead.

A client now picks a named quality (`draft`, `standard` or `high`; `standard`
by default), and the worker asks the engine for its preset of that name:
`renderMultitrack(..., preset=...)` (contract C5). The client says how good;
the engine says how. What each preset means to the encoder -- x264's speed
and constant-rate factor, the sound's bitrate -- is otto's
(`otto.render.PRESETS`), and none of it is here: the qualities and otto's
presets share their names, so a quality passes through as it is.
"""

from dataclasses import dataclass

# The qualities a render may ask for, each the name of one of otto's presets.
QUALITIES = ('draft', 'standard', 'high')

DEFAULT_QUALITY = 'standard'


@dataclass(frozen=True)
class Preset:
    # The quality, as a render names it; otto's preset of the same name.
    name: str

    def encoder_args(self) -> dict:
        """Keyword arguments for `otto.render.renderMultitrack`."""
        return dict(preset=self.name)


PRESETS = {quality: Preset(quality) for quality in QUALITIES}


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
