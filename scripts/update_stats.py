import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / 'config.xml'
PYPI_PACKAGES = ['py-tgcalls', 'ntgcalls']
RELEASE_REPOS = ['pytgcalls/ntgcalls']
NPM_PACKAGE = 'ntgcalls'
NPM_START = datetime.date(2023, 7, 1)
CRATE = 'ntgcalls'
OWN_REPOS = ['pytgcalls/pytgcalls', 'pytgcalls/ntgcalls']
OTHER_REPOS = ['MarshalX/tgcalls']
OFFICIAL_SUBMODULE_QUERY = '"TelegramMessenger/tgcalls" filename:.gitmodules'
USER_AGENT = 'Mozilla/5.0 (compatible; docs-stats)'


def fetch(url, token=None):
    headers = {'User-Agent': USER_AGENT}
    if token and url.startswith('https://api.github.com'):
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read().decode()


def pypi_downloads(package):
    match = re.search(r'\d{1,3}(?:,\d{3})+', fetch(f'https://pepy.tech/projects/{package}'))
    if match is None:
        raise RuntimeError(f'No download total found for {package} on pepy.tech')
    return int(match.group(0).replace(',', ''))


def release_downloads(repo, token):
    total = 0
    page = 1
    while True:
        releases = json.loads(fetch(f'https://api.github.com/repos/{repo}/releases?per_page=100&page={page}', token))
        if not releases:
            return total
        total += sum(asset['download_count'] for release in releases for asset in release['assets'])
        page += 1


def npm_downloads(package):
    total = 0
    start = NPM_START
    today = datetime.date.today()
    while start <= today:
        end = min(start + datetime.timedelta(days=540), today)
        total += json.loads(fetch(f'https://api.npmjs.org/downloads/point/{start}:{end}/{package}')).get('downloads', 0)
        start = end + datetime.timedelta(days=1)
    return total


def crate_downloads(crate):
    return json.loads(fetch(f'https://crates.io/api/v1/crates/{crate}'))['crate']['downloads']


def dependents(repo):
    page = re.sub(r'\s+', ' ', fetch(f'https://github.com/{repo}/network/dependents'))
    match = re.search(r'([\d,]+) Repositories', page)
    return int(match.group(1).replace(',', '')) if match else 0


def code_search_count(query, token):
    if not token:
        return 0
    url = 'https://api.github.com/search/code?q=' + urllib.request.quote(query)
    return json.loads(fetch(url, token))['total_count']


def collect(token):
    downloads = {package: pypi_downloads(package) for package in PYPI_PACKAGES}
    downloads.update({repo: release_downloads(repo, token) for repo in RELEASE_REPOS})
    downloads['npm'] = npm_downloads(NPM_PACKAGE)
    downloads['crates.io'] = crate_downloads(CRATE)
    own = {repo: dependents(repo) for repo in OWN_REPOS}
    others = {repo: dependents(repo) for repo in OTHER_REPOS}
    others['TelegramMessenger/tgcalls'] = code_search_count(OFFICIAL_SUBMODULE_QUERY, token)
    own_total = sum(own.values())
    return {
        'downloads': downloads,
        'downloads_total': sum(downloads.values()),
        'dependents': own,
        'dependents_total': own_total,
        'other_dependents': others,
        'preference': own_total / (own_total + sum(others.values())) * 100,
    }


def format_points(stats):
    return [
        f'{stats["downloads_total"] // 1_000_000} MLN+',
        f'{stats["dependents_total"] // 1000 * 1000:,}+',
        f'{stats["preference"]:.1f}%',
    ]


def write_config(points):
    text = CONFIG.read_text()
    start = text.index('<numeric-pres-points>')
    end = text.index('</numeric-pres-points>')
    section = text[start:end]
    titles = iter(points)
    section = re.sub(r'title="[^"]*"', lambda match: f'title="{next(titles)}"', section)
    section = re.sub(r'Based on GitHub stats \d{4}', f'Based on GitHub stats {datetime.date.today().year}', section)
    CONFIG.write_text(text[:start] + section + text[end:])


def github_token():
    token = os.environ.get('GITHUB_TOKEN')
    if token or shutil.which('gh') is None:
        return token
    result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
    return result.stdout.strip() or None


def main():
    parser = argparse.ArgumentParser(description='Refresh the numbers shown on the documentation home page.')
    parser.add_argument('--dry-run', action='store_true', help='print the values without updating config.xml')
    args = parser.parse_args()

    stats = collect(github_token())
    points = format_points(stats)
    print(json.dumps(stats, indent=2))
    print('Home page values:', ', '.join(points))
    if not stats['other_dependents']['TelegramMessenger/tgcalls']:
        print('Log in with gh or set GITHUB_TOKEN to include the official tgcalls submodules in the preference share.')
    if not args.dry_run:
        write_config(points)
        print(f'Updated {CONFIG.name}')


main()
