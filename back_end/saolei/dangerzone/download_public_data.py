"""Download a resumable, public-only metadata snapshot. Never sends writes.

Run from back_end/saolei: python -m dangerzone.download_public_data
"""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
import time

import certifi
import requests

from .utils import DEFAULT_SNAPSHOT_DIR, file_entry, read_json, validate_identifiers, validate_snapshot, write_json


class PublicClient:
    def __init__(self, base_url: str, interval: float = 1.25):
        self.base_url = base_url.rstrip('/')
        self.interval = max(1.25, interval)
        self.last_request = 0
        self.session = requests.Session()
        self.session.verify = certifi.where()
        self.session.headers['User-Agent'] = 'OpenMS-local-public-snapshot/1.0'

    def get(self, path: str, params: dict):
        for attempt in range(5):
            time.sleep(max(0, self.last_request + self.interval - time.monotonic()))
            response = self.session.get(f'{self.base_url}{path}', params=params, timeout=(10, 90))
            # Space requests after completion so slow responses cannot cause bursts.
            self.last_request = time.monotonic()
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == 4:
                response.raise_for_status()
                return response.json()
            retry_after = response.headers.get('Retry-After', '60')
            try:
                delay = float(retry_after)
            except ValueError:
                delay = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
            delay = max(self.interval, delay, 2 ** attempt)
            print(f'{path}: HTTP {response.status_code}; retry {attempt + 1}/4 after {delay:g}s', file=sys.stderr, flush=True)
            time.sleep(delay)
        raise RuntimeError('Unreachable retry state')

    def cached(self, target: Path, path: str, params: dict, *, hydrate_video_list: bool = True):
        cached = target.exists()
        data = read_json(target) if cached else self.get(path, params)
        if not isinstance(data, list):
            raise ValueError(f'{path} did not return a JSON array')
        if hydrate_video_list and path == '/api/userprofile/videolist' and any('timems' not in row for row in data):
            # Reconstruct the snapshot's self-contained index after the website API split.
            metadata = data
            by_id = {}
            for offset in range(0, len(metadata), 100):
                ids = ','.join(str(row['id']) for row in metadata[offset:offset + 100])
                parsed = self.get('/api/video/staticdetailbatch', {'ids': ids})
                by_id.update((row['id'], row) for row in parsed)
            data = [{**by_id[row['id']], **row} for row in metadata if row['id'] in by_id]
            cached = False
        if not cached:
            write_json(target, data)
        return data


def download_identifiers(root: Path, client: PublicClient, users: dict):
    entries = []
    seen = set()
    for index, user_id in enumerate(users, 1):
        path = root / 'identifiers' / f'{user_id}.json'
        identifiers = client.cached(path, '/api/userprofile/identifier', {'user_id': user_id})
        if isinstance(identifiers, list) and all(isinstance(text, str) for text in identifiers):
            unique_identifiers = list(dict.fromkeys(identifiers))
            if unique_identifiers != identifiers:
                identifiers = unique_identifiers
                write_json(path, identifiers)
        validate_identifiers(identifiers, seen)
        entries.append({**file_entry(root, path), 'user_id': user_id})
        print(f'Identifiers: {index}/{len(users)} users, {len(seen)} identifiers', flush=True)
    return entries, len(seen)


def download(root: Path, client: PublicClient, *, skip_details: bool = False, metadata_index: bool = False):
    if skip_details and metadata_index:
        raise ValueError('metadata_index requires full detail downloads')
    checkpoint = root / 'source.json'
    if checkpoint.exists():
        if read_json(checkpoint)['base_url'] != client.base_url:
            raise ValueError('Use a new directory when changing the source server')
    else:
        write_json(checkpoint, {'base_url': client.base_url, 'started_at': datetime.now(timezone.utc).isoformat()})
    manifest_path = root / 'manifest.json'
    if manifest_path.exists() and read_json(manifest_path).get('complete'):
        manifest, users = validate_snapshot(root)
        if manifest['version'] == 1:
            # Keep the old completed manifest intact until all new files are ready, so interrupted upgrades resume.
            entries, count = download_identifiers(root, client, users)
            manifest.update(version=2, identifiers=entries, identifier_count=count, finished_at=datetime.now(timezone.utc).isoformat())
            write_json(manifest_path, manifest)
            validate_snapshot(root)
        print(f'Already complete: {manifest["user_count"]} users, {manifest["video_count"]} videos, {manifest["identifier_count"]} identifiers')
        return

    ids = sorted(set(client.cached(root / 'user-ids.json', '/api/userprofile/infoupdated', {'since': 0})))
    manifest = {'version': 2, 'complete': False, **read_json(checkpoint), 'users': [], 'videos': [], 'identifiers': []}
    write_json(manifest_path, manifest)
    users = {}
    for offset in range(0, len(ids), 100):
        path = root / 'users' / f'{offset:06d}.json'
        rows = client.cached(path, '/api/userprofile/infobulk', {'ids': ','.join(map(str, ids[offset:offset + 100]))})
        users.update({row['id']: row for row in rows})
        manifest['users'].append(file_entry(root, path))
    print(f'Users: {len(users)}', flush=True)
    manifest['identifiers'], manifest['identifier_count'] = download_identifiers(root, client, users)

    video_index = {}
    for index, user_id in enumerate(users, 1):
        rows = client.cached(root / 'indexes' / f'{user_id}.json', '/api/userprofile/videolist', {'user_id': user_id}, hydrate_video_list=not metadata_index)
        for row in rows:
            if not row.get('ongoing_tournament'):
                video_index[row['id']] = {**row, 'player': user_id}
        print(f'Video index: {index}/{len(users)} users, {len(video_index)} public videos', flush=True)

    # Fixed id intervals preserve gaps. An empty interval is not the end of the database.
    buckets = {}
    for video_id in video_index:
        first = ((video_id - 1) // 250) * 250 + 1
        buckets.setdefault(first, []).append(video_id)
    ranges = sorted(buckets)
    downloaded = set()
    missing_details = []
    for index, first in enumerate(ranges, 1):
        raw_path = root / 'raw-videos' / f'{first:09d}.json'
        if skip_details:
            rows = read_json(raw_path) if raw_path.exists() else []
        else:
            rows = client.cached(raw_path, '/api/video/detailbulk', {'first': first, 'count': 250})
        details = {row['id']: row for row in rows}
        video_ids = buckets[first] if skip_details else details
        records = []
        for video_id in video_ids:
            if video_id not in video_index:
                continue
            # Reconstructed indexes provide pluck and right_ce even when cached details lack them.
            video = {**video_index[video_id], **details.get(video_id, {})}
            if video.get('right_ce') is None:
                video['right_ce'] = video_index[video_id].get('right_ce')
            if video['player'] not in users or video.get('ongoing_tournament'):
                continue
            if video_id not in details:
                missing_details.append(video_id)
            records.append(video)
            downloaded.add(video['id'])
        path = root / 'videos' / f'{first:09d}.json'
        write_json(path, records)
        manifest['videos'].append(file_entry(root, path))
        print(f'Details: {index}/{len(ranges)} ranges, {len(downloaded)} videos', flush=True)

    manifest.update(user_count=len(users), video_count=len(downloaded), complete=True, finished_at=datetime.now(timezone.utc).isoformat(), unavailable_video_ids=sorted(set(video_index) - downloaded), missing_detail_video_ids=sorted(missing_details))
    write_json(manifest_path, manifest)
    validate_snapshot(root)
    print(f'Complete: {len(users)} users, {len(downloaded)} videos, {manifest["identifier_count"]} identifiers; unavailable after indexing: {len(manifest["unavailable_video_ids"])}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://openms.top')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument('--interval', type=float, default=1.25)
    parser.add_argument('--skip-details', action='store_true', help='Use cached details when available, otherwise use public video lists (including right_ce for NF); do not request detailbulk')
    parser.add_argument('--metadata-index', action='store_true', help='Skip parsed-field hydration of video lists; detailbulk still supplies TPE inputs, but omitted fields such as pluck remain NULL')
    args = parser.parse_args()
    if not args.base_url.startswith('https://'):
        parser.error('Public downloads require HTTPS')
    try:
        download(args.output_dir, PublicClient(args.base_url, args.interval), skip_details=args.skip_details, metadata_index=args.metadata_index)
    except (requests.RequestException, OSError, ValueError) as error:
        print(f'Download stopped; rerun to resume: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
