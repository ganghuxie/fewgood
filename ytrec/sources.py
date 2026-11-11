"""Load the repo-static source table from ``config/sources.yaml``.

The table is the authoritative list of curated channels and the single HN
community source.  Feed builders still accept the legacy per-topic YAML files
so existing callers keep working; the helpers here union both representations.
"""
from pathlib import Path

import yaml

DEFAULT_SOURCES = 'config/sources.yaml'
SOURCE_TOPICS = ('ai', 'podcast', 'music', 'editorial', 'community')


def load_sources(path=None):
    """Return every source row from ``sources.yaml``."""
    target = Path(path or DEFAULT_SOURCES)
    payload = yaml.safe_load(target.read_text()) or {}
    return payload.get('sources') or []


def sources_for_topic(topic, sources=None, path=None, status='active'):
    """Return source rows that may feed ``topic`` (and match ``status``)."""
    rows = load_sources(path) if sources is None else sources
    return [
        source for source in rows
        if topic in (source.get('topics') or [])
        and (status is None or source.get('status') == status)
    ]


def channel_sources_for_topic(topic, sources=None, path=None, status='active'):
    """Return active channel rows for a topic that have a YouTube id."""
    return [
        source for source in sources_for_topic(topic, sources=sources, path=path, status=status)
        if source.get('type') == 'channel' and source.get('external_id')
    ]


def channel_from_source(source):
    """Map a sources.yaml row to the legacy channel-config shape."""
    return {
        'name': source.get('display_name') or source.get('id'),
        'youtube_channel_id': source.get('external_id'),
        'handle': source.get('handle') or '',
        '_source_id': source.get('id'),
    }


def channels_for_topic(topic, legacy_channels=(), path=None, status='active'):
    """Union legacy channel rows with active sources.yaml rows for ``topic``.

    Legacy rows come first so their display names/handles remain stable.  Rows
    are deduplicated by YouTube channel id; the two intentional Latent Space
    ids remain distinct because they are different channels.
    """
    merged = []
    seen = set()
    for channel in legacy_channels or ():
        channel_id = channel.get('youtube_channel_id')
        if channel_id and channel_id in seen:
            continue
        if channel_id:
            seen.add(channel_id)
        merged.append(dict(channel))
    for source in channel_sources_for_topic(topic, path=path, status=status):
        channel_id = source.get('external_id')
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)
        merged.append(channel_from_source(source))
    return merged
