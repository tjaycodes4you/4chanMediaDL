# RUNNING_LOG

## 2026-11-11

### F1 — i.4cdn.org rate-limits hard, and the old code hid it `working_assumption`

- 235 assets in `https://boards.4chan.org/gif/thread/31395163`; 114 downloaded, then
  **0 errors, 0 skips** in `logs/app.LOG` and the GUI said `DONE - 114 files`.
- Direct probe of a missing asset: `HTTP 429`, `retry-after: 3121`, `server: cloudflare`
  (~52 min window). Burst was 30 concurrent downloads, ~14 req/s.
- Root cause: `send_request`'s 429 branch slept then `continue`d out of a `tries=1`
  loop, returning `None` with no log line; `download_image` returned without calling
  `on_done`, so the failure never reached the GUI.

### Fixes

- `utils/tools.py` — 429 now logs `Rate limited by [host] - Retry-After Ns` and only
  sleeps when a retry actually remains; refuses waits >120 s instead of parking.
- `main.py` — concurrency 30 → 4 with 0.2 s pacing; a missing response is logged and
  reported as `failed`.
- `gui.py` — failures counted separately (`DONE - N files - M failed`), `[FAIL]` per file.
- `main.py` + `gui.py` — rotating proxy pool (`host:port[:user:pass]`, `scheme://...`,
  or a `.txt` path) usable from the GUI box or `-p/--proxy`, `--proxy-file`. Page fetch
  falls back to direct if a pool line fails; media always uses the pool.

### Verified

- Through 3 lines of `antP/user_data/bypassproxies.txt`: 6 assets that 429'd direct
  downloaded fine (3.4–4.2 MB each).
- `set_proxies` on the full 1000-line pool: 3.19 s, 1000 clients.
- GUI relaunched and rendered with the new PROXY POOL section.

### Proxy pool persistence

- Saved to `user_data/proxies.txt` on DOWNLOAD and on window close; loaded into the
  box at startup. `user_data/` is gitignored (`git check-ignore` verified) so creds
  never enter the repo.

