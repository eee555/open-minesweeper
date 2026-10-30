"""Reset local test data from a public snapshot; creates today's weekly tournament.

Admin: id=2, password=admin123456. Normal user: id=48, password=user123456.
Usernames come from the snapshot. This script needs no running HTTP server.
Restores user identifiers and their ownership, then rebuilds Saolei, PB, top, Thrp and NF IOE rankings.
Run from back_end/saolei: python -m dangerzone.init_local_test
"""
import argparse
import os
from pathlib import Path
import sys

import django
from django.core.management.base import CommandError

from .utils import DEFAULT_SNAPSHOT_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument('--admin-password', default='admin123456')
    parser.add_argument('--user-password', default='user123456')
    parser.add_argument('--no-weekly', action='store_true', help='Do not create a local weekly tournament')
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saolei.settings')
    django.setup()
    # Models must be imported after Django's app registry is initialized.
    from .public_snapshot import initialize_local_data

    try:
        initialize_local_data(
            args.snapshot_dir.resolve(), args.admin_password, args.user_password,
            stdout=sys.stdout, create_weekly=not args.no_weekly,
        )
    except CommandError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
