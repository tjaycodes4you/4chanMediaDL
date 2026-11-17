import asyncio
import datetime
import json
from logging import Logger
from random import randint
from urllib.parse import urlparse

import wreq
from wreq import Client, Jar, Proxy, Response, Emulation, Multipart, OrigHeaderMap
from wreq.exceptions import RequestError
from wreq.redirect import Policy


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
    client = Client(
        emulation=Emulation.Chrome145,
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
                    retry_after = resp.headers.get('retry-after')
                    try:
                        wait = int(bytes(retry_after)) if retry_after else randint(*four_two_nine_delay)
                    except (TypeError, ValueError):
                        wait = randint(*four_two_nine_delay)
                    if _try + 1 >= tries or wait > 120:
                        log.warning(
                            f"Rate limited by [{urlparse(url).netloc}] - HTTP 429 - Retry-After {wait}s")
                        return None
                    log.warning(f"Rate limited by [{urlparse(url).netloc}] - HTTP 429 - sleeping {wait}s")
                    await asyncio.sleep(wait)
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
