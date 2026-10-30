"""Where a finished render goes: each destination an adapter behind one seam.

alfred owns which destination a render is bound for, whether it got there, and
what the caller gets back; the transport is the adapter's. The seam is the one
the adoption record asks object storage to be reached through, rather than a
vendor SDK (`bucket.py`, behind `BucketDestination`).
"""

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile
from typing import Protocol

from alfred import config


class DeliveryError(Exception):
    """A destination could not accept a render. The render itself is fine, so
    this is worth retrying, as a failed render is not."""


class UnknownDestination(DeliveryError):
    """No destination has that name: asking again will not deliver it."""


@dataclass(frozen=True)
class Delivery:
    """What a caller gets back, whatever the destination was.

    `location` lasts: a path, or a `gs://` reference. It becomes a link (signed,
    for the bucket) when it is handed out.
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
    """Keep the render on this machine, under DELIVERY_DIR: the default, and
    all a server without a cloud account has. Never anywhere served
    statically; its owner gets it back through the download route."""

    name = 'local'

    def __init__(self, root=None):
        self.root = Path(root or config.DELIVERY_DIR)

    def deliver(self, filename: str) -> Delivery:
        source = Path(filename)
        if not source.is_file():
            raise DeliveryError(f'no such render: {filename}')
        if _inside(self.root, config.STATIC_DIR):
            # The SPA's directory is public: no setting may publish a render.
            raise DeliveryError(
                'the delivery directory is inside STATIC_DIR, which is served '
                'publicly; set ALFRED_DELIVERY_DIR somewhere else'
            )
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / source.name
        # Copy, not move: the worker may hold the file, and a retry needs it.
        copyfile(source, target)
        return Delivery(destination=self.name, location=str(target))


class BucketDestination:
    """Google Cloud Storage, behind the seam. `bucket` is imported in the
    method, so no other destination needs the cloud SDK."""

    name = 'bucket'

    def deliver(self, filename: str) -> Delivery:
        """Upload the file as an object of its own name, as the worker's upload
        names it, and locate it as `gs://<bucket>/<object>`: a signed URL
        would be dead in fifteen minutes."""
        from .bucket import object_reference, upload

        source = Path(filename)
        try:
            upload(source.name, directory=str(source.parent))
        except Exception as exc:  # noqa: BLE001 - vendor SDK raises broadly
            raise DeliveryError(f'upload failed: {exc}') from exc
        return Delivery(destination=self.name, location=object_reference(source.name))


DESTINATIONS = {
    LocalDestination.name: LocalDestination,
    BucketDestination.name: BucketDestination,
}

# What the editor offers. The bucket stays reachable by name, not offered
# until its credentials and the adoption record's vendor questions are settled.
OFFERED_DESTINATIONS = (LocalDestination.name,)

DEFAULT_DESTINATION = LocalDestination.name


def get_destination(name=None) -> Destination:
    """Resolve a destination by name. An unknown one raises rather than
    falling back: a typo should stop a delivery, not send it elsewhere."""
    chosen = name or DEFAULT_DESTINATION
    if chosen not in DESTINATIONS:
        raise UnknownDestination(
            f'unknown destination {chosen!r}; known: {sorted(DESTINATIONS)}'
        )
    return DESTINATIONS[chosen]()
