import asyncio
import datetime
import json
from logging import Logger
from random import shuffle, randint
from urllib.parse import urlparse

import wreq
from wreq import Client, Jar, Response, Proxy, Emulation, Multipart, OrigHeaderMap, TlsOptions
from wreq.exceptions import RequestError
from wreq.http2 import Http2Options, PseudoOrder, PseudoId
from wreq.redirect import Policy

from utils.root import get_project_root


# Proxy stuff
def load_proxies():
    """Legacy proxy loader - kept for backward compatibility."""
    global RAW_PROXIES
    with open(f'{get_project_root()}/user_data/proxies.txt', 'r', encoding='utf-8') as f:
        RAW_PROXIES = [line.strip().split(':') for line in f.readlines() if line.strip()]


async def async_cycle():
    """Legacy proxy cycling - kept for backward compatibility."""
    saved_items = RAW_PROXIES
    shuffle(saved_items)
    if not saved_items:
        return
    while True:
        for item in saved_items:
            yield item


async def get_next_proxy():
    return await PROXIES.__anext__()


async def test_next_proxy():
    for _ in range(20):
        print(await get_next_proxy())


# load_proxies()
# PROXIES = async_cycle()


def build_proxy_url(raw_proxy: list[str] | None) -> str | None:
    if not raw_proxy or len(raw_proxy) < 4:
        return None
    ip, port, user, password = raw_proxy[:4]
    if not all([ip, port]):
        return None
    credentials = ''
    if user and password:
        credentials = f'{user}:{password}@'
    return f'http://{credentials}{ip}:{port}'


# request client
def rnet_client(proxy: str | None = None,
                allow_redirects: bool = True,
                jar: Jar | None = None,
                verify: bool = True) \
        -> Client | tuple[Jar, Client]:
    if proxy:
        proxy = [Proxy.all(proxy)]
    if not jar:
        jar = Jar()
    orig_headers = [
        "content-length",
        "cache-control",
        "sec-ch-ua-platform",
        "x-xsrf-token",
        "user-agent",
        "if-modified-since",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "accept",
        "origin",
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
        "referer",
        "accept-encoding",
        "accept-language",
        "cookie",
        "priority"
    ]
    if allow_redirects:
        allow_redirects = Policy.limited()
    else:
        allow_redirects = Policy.none()
    http2_options = Http2Options(
        initial_window_size=65535,  # Conservative window size
        max_frame_size=16384,  # Standard frame size
        header_table_size=4096,  # Smaller header table
        max_concurrent_streams=100,  # Limit concurrent streams
        enable_push=False,  # Disable server push
    )
    tls_options = TlsOptions(
        grease_enabled=True,  # Send GREASE extensions
        permute_extensions=True,  # Randomize extension order
        enable_ocsp_stapling=True,  # Enable OCSP stapling
    )
    # Create custom pseudo-header order
    pseudo_order = PseudoOrder(
        PseudoId.METHOD,
        PseudoId.AUTHORITY,
        PseudoId.SCHEME,
        PseudoId.PATH,
    )

    # Apply to HTTP/2 options
    http2_options = Http2Options(
        headers_pseudo_order=pseudo_order
    )
    client = Client(
        emulation=Emulation.Chrome145,
        # http2_options=http2_options,
        # tls_options=tls_options,
        # http1_only=True,
        # tls_options=chrome_144_tls(),
        proxies=proxy,
        verify=verify,
        redirect=allow_redirects,
        timeout=datetime.timedelta(seconds=60),
        orig_headers=orig_headers,
        cookie_provider=jar,
    )
    return client


async def send_request(
        client: Client,
        headers: dict,
        url: str,
        orig_header_map: OrigHeaderMap = None,
        four_two_nine_delay: list[int] = None,
        log: Logger = None,
        timeout: int = datetime.timedelta(seconds=90),
        method: str = 'GET',
        tries: int = 1,
        delay: int | float = 3,
        json_body: dict = None,
        form: dict[str, str | int] | list = None,
        good_statuses: list[int] = None,
        return_json: bool = False,
        return_status: bool = False,
        return_resp: bool = False,
        jar: Jar | None = None,
        multipart: Multipart | None = None,
        data: bytes | str | None = None,
        redirect: Policy = Policy.limited(),
        version: wreq.Version = wreq.Version.HTTP_2
) -> str | dict | None | tuple[str, int] | tuple[dict, int] | Response:
    if not log:
        log = LOG
    if not good_statuses:
        good_statuses = [200]
    if not four_two_nine_delay:
        four_two_nine_delay = [10, 15]
    to_return, resp = None, None
    timeout = datetime.timedelta(seconds=timeout) if type(timeout) in [int, float] else timeout
    for _try in range(tries):
        try:
            # LOG.debug(f"Try #{_try + 1} - Sending [{method}] request to [{url}]. "
            #           f"Len JSON - [{len(json_body) if json_body else 0}]. "
            #           f"Len Form - [{len(form) if form else 0}]. "
            #           f"Len Data - [{len(data) if data else 0}]")
            # LOG.debug(f'Multipart: {multipart}')
            if jar:
                cookies = {cookie.name: cookie.value
                           for cookie in jar.get_all()
                           if not cookie.domain or urlparse(url).netloc.split('.')[-2].lower() in cookie.domain.lower()}
                # if method == 'GET':
                #     resp = await client.get(url, headers=headers, timeout=timeout, cookies=cookies,
                #                             default_headers=False, orig_headers=orig_header_map, redirect=redirect)
                # elif method == 'POST':
                #     if data is not None:
                #         resp = await client.post(url, headers=headers, body=data, timeout=timeout,
                #                                  cookies=cookies, default_headers=False, orig_headers=orig_header_map,
                #                                  redirect=redirect)
                #     else:
                #         resp = await client.post(url, headers=headers, json=json_body, form=form, timeout=timeout,
                #                                  cookies=cookies, default_headers=False, multipart=multipart,
                #                                  orig_headers=orig_header_map, redirect=redirect)
            else:
                cookies = {}
                # print(f'added cookies:', cookies)
            if method == 'GET':
                resp = await client.get(url, headers=headers, timeout=timeout, default_headers=False,
                                        orig_headers=orig_header_map, redirect=redirect, cookies=cookies, version=version)
            elif method == 'POST':
                resp = await client.post(url, headers=headers, json=json_body, form=form, body=data, timeout=timeout,
                                         default_headers=False, multipart=multipart, orig_headers=orig_header_map,
                                         redirect=redirect, cookies=cookies, version=version)
            elif method == 'PUT':
                resp = await client.put(url, headers=headers, json=json_body, form=form, body=data, timeout=timeout,
                                        default_headers=False, multipart=multipart, orig_headers=orig_header_map,
                                        redirect=redirect, cookies=cookies, version=version)
            if (status := resp.status.as_int()) not in good_statuses:
                if status == 429:
                    four_two_nine_delay = randint(*four_two_nine_delay)
                    # LOG.warning(
                    #     f"Try #{_try} - HTTP request failed for {method} on {url} - Status Code - {resp.status}."
                    #     f" Sleeping for {four_two_nine_delay} seconds.")
                    await asyncio.sleep(four_two_nine_delay)
                    continue
                log.error(
                    f"Try #{_try} - HTTP request failed for {method} on {url} - Status Code: {resp.status}")
                if return_resp:
                    return resp
                return None

            if jar:
                for cookie in resp.cookies:
                    jar.add(cookie, resp.url)
            if return_json:
                text = await resp.text()
                # print(url, '-', text)
                to_return = json.loads(text)
                # with open("keepa_response.json", "w") as f:
                #     json.dump(to_return, f, indent=4)
            elif return_resp:
                to_return = resp
            else:
                text = await resp.text()
                to_return = text
            # LOG.debug(f"Try #{_try + 1} - Sent [{method}] request to [{url}] - status [{resp.status}]. "
            #           f"Len JSON - [{len(json_body) if json_body else 0}]. "
            #           f"Len Form - [{len(form) if form else 0}]. "
            #           f"Len Data - [{len(data) if data else 0}]")
            if 'discord' in url:
                return None
            if to_return:
                if return_status:
                    return to_return, resp.status.as_int()
                return to_return
            await asyncio.sleep(delay)
        except RequestError as e:
            log.error(f"Try #{_try} - HTTP request failed for {method} on {url}: {e}")
        except Exception as e:
            log.exception(e)
            log.error(f"Try #{_try} - HTTP request failed for {method} on {url}, Unrecognized error: {e}")
    return None


def ensure_webhook_client():
    global WEBHOOK_CLIENT
    if not WEBHOOK_CLIENT:
        WEBHOOK_CLIENT = rnet_client(proxy=None)


async def send_webhook(url: str | None, title: str, color: int, fields: list[dict], file_content: str | None = None, filename: str = "traceback.txt"):
    """
    Light Blue: 11393254 (Hex: #ADD8E6)
    Light Green: 9498256 (Hex: #90EE90)
    {"name": "Event", "value": "Ice Hockey Final", "inline": True}

    Args:
        url: Discord webhook URL
        title: Embed title
        color: Embed color (integer)
        fields: List of embed fields
        file_content: Optional text content to upload as a file (e.g., traceback)
        filename: Name of the file to upload (default: traceback.txt)
    """
    global WEBHOOK_CLIENT
    if not WEBHOOK_CLIENT:
        WEBHOOK_CLIENT = rnet_client(
            # proxy='http://localhost:8888', verify=False
        )
    payload = {
        "embeds": [
            {
                # "content": "@everyone",
                "title": title,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "Olympics LA Bot - [@tjaycodes4you]",
                    "icon_url": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQqqCwwKUibRgUj0Eu4jusRmJnM3i4pEpF0UQ&s"
                },
                "timestamp": datetime.datetime.utcnow().isoformat(timespec='milliseconds')
            }
        ]
    }

    # Send to provided URL if exists
    if file_content:
        # Use multipart upload with file attachment for Discord webhooks
        payload_part = wreq.Part(
            name="payload_json",
            value=json.dumps(payload),
            mime="application/json"
        )
        file_part = wreq.Part(
            name="file",
            value=file_content,
            filename=filename,
            mime="text/plain"
        )
        multipart = wreq.Multipart(payload_part, file_part)

        task = send_request(
            WEBHOOK_CLIENT,
            url=url,
            method='POST',
            headers={},
            multipart=multipart,
            good_statuses=[200, 204]
        )
    else:
        task = send_request(
            WEBHOOK_CLIENT,
            url=url,
            method='POST',
            json_body=payload,
            good_statuses=[200, 204],
            headers={"Content-Type": "application/json"}
        )

    async with WEBHOOK_SEM:
        await task


if __name__ == '__main__':
    pass
