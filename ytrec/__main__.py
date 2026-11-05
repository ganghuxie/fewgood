import argparse
import json
import subprocess
from pathlib import Path
import yaml
from .core import connect, crawl, extract, aggregate, enrich, report, stamp, now

def main():
    parser = argparse.ArgumentParser(description='HN → repeated YouTube recommendations')
    parser.add_argument('command', choices=['crawl','extract','aggregate','enrich','report','build-site','all'])
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--start', help='Inclusive UTC ISO date')
    parser.add_argument('--end', help='Exclusive UTC ISO date (default now)')
    parser.add_argument('--refresh-metadata', action='store_true')
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if config['recommendation']['positive_sentiment']['enabled']:
        parser.error('Positive sentiment is deferred to phase 2; keep enabled: false')
    db = connect(config['database'])
    try:
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
