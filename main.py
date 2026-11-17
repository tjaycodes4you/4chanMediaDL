import argparse
import asyncio
import html
import itertools
import re
from asyncio import Semaphore
from pathlib import Path

from utils.custom_log_format import logger
from utils.root import get_project_root
from utils.tools import rnet_client, send_request

LOG = logger(name="main")
ROOT = Path(get_project_root())
SITE_FILE = ROOT / 'site.html'
DEFAULT_FOLDER = ROOT / 'output' / 'downloads'
DIRECT = 'direct'

CLIENT_POOL = [(DIRECT, rnet_client())]
CLIENT_CYCLE = itertools.cycle(CLIENT_POOL)


def next_client() -> tuple[str, object]:
    return next(CLIENT_CYCLE)


def parse_proxy(line: str) -> tuple[str, str] | None:
    if '://' in line:
        return line.split('://', 1)[1].split('@')[-1].split('/')[0], line
    parts = line.split(':')
    if len(parts) == 4:
        host, port, user, password = parts
        return f'{host}:{port}', f'http://{user}:{password}@{host}:{port}'
    if len(parts) == 2:
        return line, f'http://{line}'
    return None


def load_proxy_lines(value: str) -> list[str]:
    path = Path(value.strip())
    if '\n' not in value.strip() and path.is_file():
        lines = path.read_text(encoding='utf-8').splitlines()
    else:
        lines = value.splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]


def set_proxies(lines: list[str]) -> int:
    global CLIENT_POOL, CLIENT_CYCLE
    pool = []
    for line in lines:
        parsed = parse_proxy(line)
        if not parsed:
            LOG.warning(f"Ignoring malformed proxy line [{line[:48]}]")
            continue
        label, url = parsed
        try:
            pool.append((label, rnet_client(proxy=url)))
        except Exception as e:
            LOG.warning(f"Ignoring proxy [{label}]: {e}")
    CLIENT_POOL = pool or [(DIRECT, rnet_client())]
    CLIENT_CYCLE = itertools.cycle(CLIENT_POOL)
    return len(pool)

MEDIA_RE = re.compile(r'fileText.+?href="(.+?)".+?>(.+?)<')
INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')

PAGE_HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-CA,en-US;q=0.9,en-GB;q=0.8,en;q=0.7',
    'cache-control': 'no-cache',
    'dnt': '1',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://boards.4chan.org/',
    'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-storage-access': 'active',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
}

MEDIA_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-CA,en-US;q=0.9,en-GB;q=0.8,en;q=0.7',
    'cache-control': 'no-cache',
    'dnt': '1',
    'pragma': 'no-cache',
    'priority': 'i',
    'range': 'bytes=0-',
    'referer': 'https://boards.4chan.org/',
    'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'video',
    'sec-fetch-mode': 'no-cors',
    'sec-fetch-site': 'cross-site',
    'sec-fetch-storage-access': 'active',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
}


def board_from_url(url: str) -> str | None:
    match = re.search(r'boards\.4chan\.org/([^/]+)/thread/(\d+)', url)
    return match.group(1) if match else None


def parse_media(src: str) -> list[list[str]]:
    out = []
    for url, name in MEDIA_RE.findall(src):
        if not url.startswith('http'):
            url = 'https:' + url
        name = INVALID_CHARS.sub('_', html.unescape(name)).strip()
        if not name:
            continue
        out.append([url, name])
    return out


async def fetch_thread(url: str) -> str:
    label, client = next_client()
    src = await send_request(
        client=client,
        url=url,
        headers=PAGE_HEADERS,
        log=LOG,
        good_statuses=[200],
    )
    if src:
        return src
    if label == DIRECT:
        raise RuntimeError(f"Failed to fetch thread page: {url}")
    LOG.warning(f"Thread page failed via [{label}] - retrying direct")
    src = await send_request(
        client=rnet_client(),
        url=url,
        headers=PAGE_HEADERS,
        log=LOG,
        good_statuses=[200],
    )
    if not src:
        raise RuntimeError(f"Failed to fetch thread page direct: {url}")
    return src


async def download_image(url: str, name: str, output_dir: Path, sem: Semaphore, on_done=None, cancel=None):
    if cancel is not None and cancel.is_set():
        return
    target = output_dir / name
    if target.exists() and target.stat().st_size > 0:
        LOG.info(f"Skipping [{name}] - already downloaded")
        if on_done:
            on_done(name, 'skipped')
        return
    async with sem:
        await asyncio.sleep(0.2)
        label, client = next_client()
        response = await send_request(
            url=url,
            headers=MEDIA_HEADERS,
            log=LOG,
            client=client,
            good_statuses=[206],
            return_resp=True,
            tries=2,
        )
        if response is None:
            LOG.error(f"Failed [{name}] via [{label}] - no response from CDN (see rate-limit warning)")
            if on_done:
                on_done(name, 'failed')
            return
        LOG.debug(f"Downloading media [{name}]")
        async with response:
            image_bytes = await response.bytes()
            target.write_bytes(image_bytes)
        LOG.info(f"Downloaded image [{name}]")
        if on_done:
            on_done(name, 'downloaded')


async def run(url: str | None, output: str | None, on_done=None, on_total=None, cancel=None):
    if url:
        LOG.info(f"Fetching thread page [{url}]")
        src = await fetch_thread(url)
    else:
        if not SITE_FILE.exists():
            LOG.error(f"No URL provided and [{SITE_FILE}] not found")
            return
        LOG.info(f"No URL provided, parsing [{SITE_FILE}]")
        src = SITE_FILE.read_text(encoding='utf-8')

    media = parse_media(src)
    if not media:
        LOG.error("No media found")
        return

    if output:
        output_dir = Path(output)
    elif url and (board := board_from_url(url)):
        output_dir = ROOT / 'output' / board
    else:
        output_dir = DEFAULT_FOLDER
    output_dir.mkdir(parents=True, exist_ok=True)

    if on_total:
        on_total(len(media))
    LOG.info(f"Downloading [{len(media)}] files to [{output_dir}]")
    sem = Semaphore(4)
    await asyncio.gather(*(download_image(u, n, output_dir, sem=sem, on_done=on_done, cancel=cancel) for u, n in media))


def main():
    parser = argparse.ArgumentParser(description="Download all media from a 4chan thread")
    parser.add_argument('url', nargs='?', help="4chan thread URL (defaults to site.html in project root)")
    parser.add_argument('-o', '--output', help="Output folder (defaults to output/<board> or output/downloads)")
    parser.add_argument('-p', '--proxy', action='append', default=[],
                        help="Proxy line host:port[:user:pass] (repeatable)")
    parser.add_argument('--proxy-file', help="File with one proxy per line")
    args = parser.parse_args()
    lines = list(args.proxy)
    if args.proxy_file:
        lines += load_proxy_lines(args.proxy_file)
    if lines:
        LOG.info(f"Proxy pool: [{set_proxies(lines)}] line(s)")
    asyncio.run(run(args.url, args.output))


if __name__ == "__main__":
    main()
