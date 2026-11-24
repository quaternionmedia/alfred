"""How a render's `quality` becomes an encoding (contract C5).

A client names a quality (`draft`, `standard` or `high`; `standard` by
default), and the worker asks otto for its preset of that name. What a preset
means to the encoder is otto's (`otto.render.PRESETS`); no encoder option from
a client reaches ffmpeg.
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

    `strict=False` falls back to the default instead of raising, for stored
    renders with an old quality name (`web`, `TV`).
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
