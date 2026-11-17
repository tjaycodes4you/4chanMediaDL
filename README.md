# 4chanMediaDL

Pulls every image, GIF and video out of a 4chan thread — GUI or CLI — with resume,
a rotating proxy pool, and a neon terminal-style UI.

![GUI](assets/preview_dark.png)

## Features

- **GUI and CLI** from the same code path.
- **Resume built in** — files already on disk (non-zero size) are skipped, so a
  re-run only fetches what is missing.
- **Rotating proxy pool** — paste ISP/DC lines once, they persist and rotate per
  request. The thread page falls back to a direct connection if a pool line is
  refused; media always uses the pool.
- **Honest failure reporting** — per-file `[OK]` / `[SKIP]` / `[FAIL]` log, and a
  rate-limit warning naming the host and `Retry-After` instead of silently
  stopping halfway.
- **Chrome-fingerprinted transport** via [wreq](https://pypi.org/project/wreq/)
  (TLS + HTTP/2 profile, not a bare requests call).

## Requirements

- Windows (the taskbar/icon and folder-opening bits are Win32-specific).
- Python 3.11+ with Tkinter (bundled with the python.org installer).
- Dependencies: `pip install -r requirements.txt`

## Run the GUI

```sh
python gui.py
```

1. Paste a thread URL — `https://boards.4chan.org/<board>/thread/<id>`.
   Leave it empty to parse a `site.html` saved next to the project instead.
2. Pick an output directory (default `output/` in the project root).
3. Optionally paste proxies into **PROXY POOL** (see below).
4. **DOWNLOAD**. Progress bar, per-file log, and `ABORT` are all live.

The proxy list is remembered in `user_data/proxies.txt`; the output directory is
not persisted.

## Run the CLI

```sh
python main.py https://boards.4chan.org/gif/thread/31395163 -o "D:/downloads/thread"
python main.py --proxy-file user_data/proxies.txt            # uses site.html
python main.py <url> -p 1.2.3.4:8080 -p 5.6.7.8:8080:user:pass
```

| Flag | Meaning |
| --- | --- |
| `url` | Thread URL (omit to read `site.html` from the project root) |
| `-o, --output` | Output folder (default `output/<board>` or `output/downloads`) |
| `-p, --proxy` | One proxy line, repeatable |
| `--proxy-file` | File with one proxy per line |

## Proxy pool format

One entry per line. Accepted shapes:

```
host:port
host:port:user:pass
http://user:pass@host:port
socks5://user:pass@host:port
```

Pasting a **path to a `.txt`** into the GUI box loads that file instead. Invalid
lines are skipped with a warning. `user_data/` is gitignored — proxy credentials
never enter the repo.

## Notes on rate limits

`i.4cdn.org` sits behind Cloudflare and will answer `HTTP 429` with a long
`Retry-After` when hammered. This tool downloads four at a time with a small
pause and reports the window when it hits one. If you get throttled, either wait
out `Retry-After` and re-run (finished files are skipped) or rotate egress with a
proxy pool. Please don't remove the throttle to "go faster" — you will just get
blocked longer.

## Build a standalone exe

```sh
pip install pyinstaller
pyinstaller 4chanMediaDL.spec        # windowed build
pyinstaller 4chanMediaDLdbg.spec     # console build for tracebacks
```

## Project layout

```
gui.py                       CustomTkinter app (splash, titlebar, log, proxy pool)
main.py                      downloader core: parse thread HTML, fetch, write files
utils/tools.py               wreq client + request helper (429 handling)
utils/custom_log_format.py   rotating file + console logging
utils/root.py                project root resolution (script or frozen exe)
assets/                      icons, theme, splash, previews
make_assets.py               regenerates the icon/clover artwork
```

`utils/tools.py` pins `Emulation.Chrome145`; the `user-agent` / `sec-ch-ua`
strings in `main.py` must be kept in lockstep with that profile — a UA claiming a
browser version the TLS profile doesn't match is worse than an older version.
`RUNNING_LOG.md` records findings and fixed bugs.

## Legal

This is a download tool. You are responsible for what you fetch and how you use
it: respect 4chan's terms and rate limits, and don't redistribute other people's
media. No warranty; see [LICENSE](LICENSE) (MIT).
