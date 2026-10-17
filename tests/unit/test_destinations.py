"""Delivery, and the seam it happens behind.

Before this there was no seam: `bucket.py` reached Google Cloud Storage through
its vendor SDK, and that was the only way a finished render could leave the
server. The adoption record lists reaching object storage through a vendor API
rather than a protocol as an open gap; these tests pin the shape that closes
it.

The local destination is exercised with real files on disk, because the thing
worth testing about a file transport is that the bytes arrive.
"""

from dataclasses import FrozenInstanceError

import pytest

from alfred.core.utils.destinations import (
    DEFAULT_DESTINATION,
    DESTINATIONS,
    BucketDestination,
    Delivery,
    DeliveryError,
    LocalDestination,
    get_destination,
)


@pytest.fixture
def a_render(tmp_path):
    """A file standing in for a finished render."""
    path = tmp_path / 'render.mp4'
    path.write_bytes(b'not really an mp4, but really a file')
    return path


class TestLocalDelivery:
    def test_the_file_arrives(self, a_render, tmp_path):
        destination = LocalDestination(root=tmp_path / 'out')
        delivery = destination.deliver(str(a_render))

        from pathlib import Path

        assert Path(delivery.location).is_file()

    def test_the_bytes_are_unchanged(self, a_render, tmp_path):
        """The point of a transport is that it does not alter the payload."""
        from pathlib import Path

        destination = LocalDestination(root=tmp_path / 'out')
        delivery = destination.deliver(str(a_render))
        assert Path(delivery.location).read_bytes() == a_render.read_bytes()

    def test_the_source_survives(self, a_render, tmp_path):
        """Copy, not move.

        The renderer may still hold the file, and a delivery that destroys its
        own input cannot be retried -- which matters because a failed delivery
        is exactly the case worth retrying.
        """
        LocalDestination(root=tmp_path / 'out').deliver(str(a_render))
        assert a_render.is_file()

    def test_it_creates_its_directory(self, a_render, tmp_path):
        destination = LocalDestination(root=tmp_path / 'deep' / 'nested' / 'out')
        delivery = destination.deliver(str(a_render))
        from pathlib import Path

        assert Path(delivery.location).is_file()

    def test_delivering_twice_is_not_an_error(self, a_render, tmp_path):
        """Retries are the expected case, not an exceptional one."""
        destination = LocalDestination(root=tmp_path / 'out')
        first = destination.deliver(str(a_render))
        second = destination.deliver(str(a_render))
        assert first.location == second.location

    def test_a_missing_render_raises_delivery_error(self, tmp_path):
        """Not FileNotFoundError.

        A caller distinguishes "the render failed" from "the render exists and
        did not get where it was going". Letting the OS error through would
        make every caller catch a type that says nothing about delivery.
        """
        destination = LocalDestination(root=tmp_path / 'out')
        with pytest.raises(DeliveryError):
            destination.deliver(str(tmp_path / 'nothing-here.mp4'))

    def test_it_reports_which_destination_delivered(self, a_render, tmp_path):
        delivery = LocalDestination(root=tmp_path / 'out').deliver(str(a_render))
        assert delivery.destination == 'local'


class TestWhereLocalDeliveriesGo:
    """Not under DATA_DIR, which the unauthenticated /data mount serves."""

    def test_the_default_is_the_delivery_directory(self, monkeypatch, tmp_path):
        from pathlib import Path

        from alfred import config

        monkeypatch.setattr(config, 'DELIVERY_DIR', str(tmp_path / 'deliveries'))
        assert LocalDestination().root == Path(tmp_path / 'deliveries')

    def test_the_default_delivery_directory_is_not_public(self):
        from pathlib import Path

        from alfred import config

        data = Path(config.DATA_DIR).resolve()
        delivery = Path(config.DELIVERY_DIR).resolve()
        assert delivery != data and data not in delivery.parents

    def test_a_directory_inside_data_dir_is_refused(
        self, a_render, tmp_path, monkeypatch
    ):
        """Refused rather than published: no setting should make a delivery
        public by accident."""
        from alfred import config

        monkeypatch.setattr(config, 'DATA_DIR', str(tmp_path / 'data'))
        destination = LocalDestination(root=tmp_path / 'data' / 'renders')
        with pytest.raises(DeliveryError, match='DATA_DIR'):
            destination.deliver(str(a_render))
        assert not (tmp_path / 'data' / 'renders').exists()


class TestTheSeam:
    def test_the_default_is_local(self):
        """A server with no cloud account still has somewhere to put a render.

        The README calls this "a video editor that works even without a
        server". Until there was a local destination, the only finished-render
        path went to a Google bucket, so that claim did not extend to getting
        your video back.
        """
        assert DEFAULT_DESTINATION == 'local'
        assert isinstance(get_destination(), LocalDestination)

    def test_the_bucket_is_reachable_by_name(self):
        assert isinstance(get_destination('bucket'), BucketDestination)

    def test_an_unknown_destination_raises(self):
        """A typo must stop the delivery, not redirect it.

        Falling back to the default would write the render somewhere other
        than a project asked for, and report success.
        """
        with pytest.raises(DeliveryError) as excinfo:
            get_destination('dropbox')
        assert 'dropbox' in str(excinfo.value)

    @pytest.mark.parametrize('name', sorted(DESTINATIONS))
    def test_every_destination_satisfies_the_interface(self, name):
        destination = get_destination(name)
        assert isinstance(destination.name, str)
        assert callable(destination.deliver)

    def test_importing_a_local_destination_needs_no_cloud_sdk(self):
        """The bucket's imports are function-local for this reason.

        Importing google.cloud.storage at module scope would make the local
        destination -- and so every test above -- depend on a cloud SDK being
        importable and configured.
        """
        import inspect

        from alfred.core.utils import destinations

        source = inspect.getsource(destinations)
        module_level = source.split('class BucketDestination')[0]
        assert 'from google' not in module_level
        assert 'import google' not in module_level


class TestTheDeliveryRecord:
    def test_it_carries_both_destination_and_location(self):
        delivery = Delivery(destination='local', location='/data/renders/x.mp4')
        assert delivery.destination == 'local'
        assert delivery.location == '/data/renders/x.mp4'

    def test_it_is_immutable(self):
        """A delivery is a record of something that happened."""
        delivery = Delivery(destination='local', location='/x')
        # Not bare `Exception`: that passes if the assignment fails for any
        # reason at all -- including a typo in the attribute name, which would
        # make this test pass while proving nothing. `Delivery` is a frozen
        # dataclass, so the specific refusal is FrozenInstanceError.
        with pytest.raises(FrozenInstanceError):
            delivery.location = '/y'
