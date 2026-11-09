import argparse
import json
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .core import connect, crawl, extract, aggregate, enrich, report, stamp, now, trending_feed, podcast_feed, music_feed, channels_feed, resolve_ai_channels, ai_feed, quota_line
from .zh import enrich_zh

def daily_limit(config):
    return config.get('metadata', {}).get('daily_quota_limit', config.get('youtube', {}).get('daily_quota_limit', 8000))

def refresh():
    """Refresh deployable feeds, build the site, and publish only changed snapshots."""
    log = Path('logs') / f"refresh-{datetime.now(timezone.utc):%Y%m%d}.log"
    log.parent.mkdir(exist_ok=True)
    with log.open('a', encoding='utf8') as handle, redirect_stdout(handle), redirect_stderr(handle):
        print(f'=== refresh {datetime.now(timezone.utc).isoformat()} ===')
        config = yaml.safe_load(Path('config.yaml').read_text())
        limit = daily_limit(config)
        trending_feed(quota_limit=limit); ai_feed(quota_limit=limit); podcast_feed(quota_limit=limit); music_feed(quota_limit=limit); channels_feed(quota_limit=limit)
        print(quota_line(limit))
        subprocess.run(['npm', 'run', 'build'], cwd='site', check=True, stdout=handle, stderr=handle)
        paths = ['site/src/data', 'site/public/catalog.json', 'site/public/channels.json', 'site/public/search-index.json']
        changed = subprocess.run(['git', 'status', '--porcelain', '--', *paths], text=True, stdout=subprocess.PIPE, check=True).stdout
        if changed:
            subprocess.run(['git', 'add', *paths], check=True, stdout=handle, stderr=handle)
            subprocess.run(['git', 'commit', '-m', f"data: refresh {datetime.now(timezone.utc):%F}"], check=True, stdout=handle, stderr=handle)
            subprocess.run(['git', 'push', 'origin', 'HEAD'], check=True, stdout=handle, stderr=handle)
            print('Committed and pushed refreshed data.')
        else:
            print('No data or catalog changes; nothing committed.')
    print(f'Refresh log: {log}')

def main():
    parser = argparse.ArgumentParser(description='HN → repeated YouTube recommendations')
    parser.add_argument('command', choices=['crawl','extract','aggregate','enrich','enrich-zh','report','build-site','all','trending','ai','podcast','music','channels','refresh','resolve-ai-channels','topic-refresh','fewgood-r3-fetch','fewgood-r3-select','fewgood-zh-fetch','fewgood-zh-select','fewgood-podcast-estimate','fewgood-podcast-resolve','fewgood-podcast-fetch','fewgood-podcast-select'])
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--start', help='Inclusive UTC ISO date')
    parser.add_argument('--end', help='Exclusive UTC ISO date (default now)')
    parser.add_argument('--refresh-metadata', action='store_true')
    parser.add_argument('--feed', default='community')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--provider', choices=['gemini','deepseek'])
    parser.add_argument('--estimate', action='store_true', help='R3 fetch plan only')
    parser.add_argument('--unit-cap', type=int, default=250, help='R3 non-search unit cap')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--fixtures')
    parser.add_argument('--queue')
    parser.add_argument('--lock')
    parser.add_argument('--out-dir')
    args = parser.parse_args()
    if args.command == 'topic-refresh':
        from . import topics
        forwarded = []
        for flag, value in (('--fixtures', args.fixtures), ('--queue', args.queue), ('--lock', args.lock), ('--out-dir', args.out_dir)):
            if value: forwarded += [flag, value]
        if args.dry_run: forwarded.append('--dry-run')
        return topics.main(forwarded)
    if args.command in ('fewgood-r3-fetch','fewgood-r3-select'):
        from . import fewgood_r3
        forwarded=['fetch' if args.command.endswith('fetch') else 'select']
        if args.estimate: forwarded.append('--estimate')
        if args.unit_cap != 250: forwarded += ['--unit-cap', str(args.unit_cap)]
        # The public command has a deliberately separate parser so normal
        # recommendation config cannot alter the R3 quota or endpoint plan.
        return fewgood_r3.main(forwarded)
    if args.command in ('fewgood-zh-fetch','fewgood-zh-select'):
        from . import fewgood_zh
        forwarded=['fetch' if args.command.endswith('fetch') else 'select']
        if args.estimate: forwarded.append('--estimate')
        return fewgood_zh.main(forwarded)
    if args.command.startswith('fewgood-podcast-'):
        from . import fewgood_podcast
        cmd=args.command.removeprefix('fewgood-podcast-')
        forwarded=[cmd]
        if args.unit_cap != 250: forwarded += ['--unit-cap', str(args.unit_cap)]
        return fewgood_podcast.main(forwarded)
    config = yaml.safe_load(Path(args.config).read_text())
    limit = daily_limit(config)
    if args.command == 'trending':
        try: trending_feed(quota_limit=limit)
        except RuntimeError as error: parser.exit(1, f'{error}\n')
        return
    if args.command == 'resolve-ai-channels':
        try: resolve_ai_channels(quota_limit=limit)
        except RuntimeError as error: parser.exit(1, f'{error}\n')
        return
    if args.command == 'ai':
        try: ai_feed(quota_limit=limit)
        except RuntimeError as error: parser.exit(1, f'{error}\n')
        return
    if args.command in ('podcast', 'music', 'channels', 'refresh'):
        try:
            if args.command == 'podcast': podcast_feed(quota_limit=limit)
            elif args.command == 'music': music_feed(quota_limit=limit)
            elif args.command == 'channels': channels_feed(quota_limit=limit)
            else: refresh()
        except (RuntimeError, subprocess.CalledProcessError) as error:
            parser.exit(1, f'{error}\n')
        return
    if config['recommendation']['positive_sentiment']['enabled']:
        parser.error('Positive sentiment is deferred to phase 2; keep enabled: false')
    db = connect(config['database'])
    try:
        if args.command == 'enrich-zh':
            enrich_zh(db, feed=args.feed, limit=args.limit, force=args.force, provider=args.provider)
            return
        if args.command in ('crawl','all'):
            crawl(db, config, stamp(args.start or config['crawl']['start']), stamp(args.end) if args.end else now())
        if args.command in ('extract','all'):
            extract(db)
        videos = aggregate(db)
        if args.command == 'aggregate':
            Path('data').mkdir(exist_ok=True)
            Path('data/aggregates.json').write_text(json.dumps(videos, indent=2))
            print(f'Aggregated {len(videos)} videos → data/aggregates.json')
        if args.command in ('enrich','all'):
            enrich(db, config, videos, args.refresh_metadata)
        if args.command in ('report','build-site','all'):
            report(db, config, videos)
        if args.command in ('build-site','all'):
            subprocess.run(['npm','run','build'], cwd='site', check=True)
    except (RuntimeError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    finally:
        db.close()

if __name__ == '__main__':
    main()
