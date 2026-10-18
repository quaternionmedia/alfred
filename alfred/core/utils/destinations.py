"""Where a finished render goes.

The control plane owns delivery as a lifecycle concern: which destination a
render is bound for, whether it got there, and what to hand back to the caller.
It does not own the transport itself -- each destination is a small adapter
behind one interface.

The interface exists because there was not one. `bucket.py` reaches Google
Cloud Storage through its vendor SDK directly, and every caller that wanted a
finished render had to know that. The adoption record lists that as an open
gap: object storage should be reached through a protocol seam rather than a
vendor API. This is the seam; the bucket becomes one implementation behind it
rather than the only way out.

`LocalDestination` is implemented fully. `BucketDestination` wraps what already
existed, so nothing about the Google path changes -- it just stops being the
only shape delivery can take, which is what makes it replaceable later.
"""

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile
from typing import Protocol

from alfred import config


class DeliveryError(Exception):
    """A destination could not accept a render.

    Distinct from "the render failed": the file exists, and getting it to its
    destination is what did not work. Callers act on that difference -- a
    failed delivery is worth retrying, a failed render is not.
    """


@dataclass(frozen=True)
class Delivery:
    """What a caller gets back, whatever the destination was.

    `location` is a URL for remote destinations and a path for local ones. It
    is deliberately not typed as one or the other: a caller that can only
    handle URLs would be coupled to a particular destination, which is what
    the seam exists to avoid.
    """

    destination: str
    location: str


class Destination(Protocol):
    """Somewhere a finished render can be delivered.

    Deliberately narrow. Anything wider -- listing, deleting, browsing -- would
    have to be implemented by every future destination, and no caller needs it
    yet. Adding a method later is easy; removing one from a published interface
    is not.
    """

    name: str

    def deliver(self, filename: str) -> Delivery:
        """Put the named render where this destination keeps things."""
        ...


def _inside(path, directory) -> bool:
    """Whether `path` is `directory` or somewhere beneath it."""
    path, directory = Path(path).resolve(), Path(directory).resolve()
    return path == directory or directory in path.parents


class LocalDestination:
    """Keep the render on this machine, under DELIVERY_DIR.

    The useful default for development and for anyone running Alfred without a
    cloud account -- the README's "cloud storage optional". Until now the only
    finished-render path went to a Google bucket, so a server without one had
    no way to give your video back.

    Not anywhere the app serves statically. This used to copy into DATA_DIR,
    which an unauthenticated mount served at /data, so every local delivery
    was a public URL for somebody's video. The video comes back to its owner
    through the download route instead.
    """

    name = 'local'

    def __init__(self, root=None):
        self.root = Path(root or config.DELIVERY_DIR)

    def deliver(self, filename: str) -> Delivery:
        source = Path(filename)
        if not source.is_file():
            raise DeliveryError(f'no such render: {filename}')
        if _inside(self.root, config.STATIC_DIR):
            # Refused rather than written: the SPA's directory is served to
            # anyone, so a delivery there would be published, which no
            # setting should be able to do by accident.
            raise DeliveryError(
                'the delivery directory is inside STATIC_DIR, which is served '
                'publicly; set ALFRED_DELIVERY_DIR somewhere else'
            )
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / source.name
        # copy, not move: the renderer may still be holding the file, and a
        # delivery that destroys its own input cannot be retried.
        copyfile(source, target)
        return Delivery(destination=self.name, location=str(target))


class BucketDestination:
    """The existing Google Cloud Storage path, behind the interface.

    Imports are function-local on purpose. `bucket.py` constructs a storage
    client at call time and expects credentials to be present; importing it at
    module scope would make every destination -- including the local one --
    depend on a cloud SDK being importable and configured.
    """

    name = 'bucket'

    def deliver(self, filename: str) -> Delivery:
        """Upload the file as an object named for it, and sign a link to it.

        This uploaded the object under the full server path and then asked
        `generate_signed_url` -- which takes a render *id* -- to sign that
        path, so it answered 422 "Not a valid identifier" after every
        successful upload. The object is named by the file's own name, as the
        worker's automatic upload names it, and signed by that name.
        """
        from .bucket import signed_url, upload

        source = Path(filename)
        try:
            upload(source.name, directory=str(source.parent))
            location = signed_url(source.name)
        except Exception as exc:  # noqa: BLE001 - vendor SDK raises broadly
            raise DeliveryError(f'upload failed: {exc}') from exc
        return Delivery(destination=self.name, location=location)


DESTINATIONS = {
    LocalDestination.name: LocalDestination,
    BucketDestination.name: BucketDestination,
}

# What the editor offers. Cloud delivery is the next phase, so the bucket stays
# implemented and reachable by name -- the seam is only worth having with more
# than one implementation behind it -- but is not presented as a choice until
# credentials, failure handling and the SSPL/vendor questions in the adoption
# record have been worked through. Offering a destination that needs a service
# account nobody has configured is a button that fails.
OFFERED_DESTINATIONS = (LocalDestination.name,)

DEFAULT_DESTINATION = LocalDestination.name


def get_destination(name=None) -> Destination:
    """Resolve a destination by name.

    Unknown names raise rather than falling back to the default: a typo in a
    project's saved settings should stop the delivery and say so, not quietly
    write somewhere else.
    """
    chosen = name or DEFAULT_DESTINATION
    if chosen not in DESTINATIONS:
        raise DeliveryError(
            f'unknown destination {chosen!r}; known: {sorted(DESTINATIONS)}'
        )
    return DESTINATIONS[chosen]()
