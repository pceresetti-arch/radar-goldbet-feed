import json
import os
import pathlib
import time
import urllib.error
import urllib.request

DEFAULT_HEADERS = {
    'Accept': 'application/json,text/plain,*/*',
    'x-api-version': '1.0',
    'X-Auth-Token': '',
    'X-Brand': '3',
    'X-IdCanale': '0',
    'Origin': 'https://www.betflag.it',
    'Referer': 'https://www.betflag.it/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36',
}


class BetFlagTransport:
    """BetFlag transport with residential browser-session recovery.

    Fast path: normal HTTP. If Akamai returns 401/403/429, bootstrap a real
    Chrome/Edge session on the residential runner and execute subsequent API
    calls inside the BetFlag browser origin. This preserves browser cookies,
    TLS/client characteristics and anti-bot session state without inventing a
    non-BetFlag fallback source.
    """

    def __init__(self, timeout=20):
        self.timeout = timeout
        self.mode = 'http'
        self.blocked_statuses = []
        self.browser_bootstraps = 0
        self.browser_errors = []
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        root = pathlib.Path(os.getenv('BETFLAG_RADAR_ROOT', r'C:\BetFlagRadar' if os.name == 'nt' else '.betflag-radar'))
        root.mkdir(parents=True, exist_ok=True)
        self.storage_state = root / 'betflag-browser-storage-state.json'

    def _http_get(self, url):
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.status, json.loads(r.read().decode('utf-8'))

    def _start_browser(self):
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError('Playwright unavailable for BetFlag browser recovery') from e

        self._pw = sync_playwright().start()
        launch_errors = []
        for channel in ('chrome', 'msedge'):
            try:
                self._browser = self._pw.chromium.launch(
                    channel=channel,
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled'],
                )
                break
            except Exception as e:
                launch_errors.append(f'{channel}: {e!r}')
        if self._browser is None:
            self._pw.stop()
            self._pw = None
            raise RuntimeError('No installed Chrome/Edge usable for BetFlag recovery: ' + '; '.join(launch_errors))

        kwargs = {
            'locale': 'it-IT',
            'timezone_id': 'Europe/Rome',
            'user_agent': DEFAULT_HEADERS['User-Agent'],
            'viewport': {'width': 1440, 'height': 1000},
            'extra_http_headers': {'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8'},
        }
        if self.storage_state.exists():
            try:
                kwargs['storage_state'] = str(self.storage_state)
            except Exception:
                pass
        try:
            self._context = self._browser.new_context(**kwargs)
        except Exception:
            kwargs.pop('storage_state', None)
            self._context = self._browser.new_context(**kwargs)

        self._page = self._context.new_page()
        self.browser_bootstraps += 1
        response = self._page.goto(
            'https://www.betflag.it/sport',
            wait_until='domcontentloaded',
            timeout=45000,
        )
        self._page.wait_for_timeout(3500)
        status = response.status if response else None
        if status and status >= 500:
            raise RuntimeError(f'BetFlag browser bootstrap HTTP {status}')
        self.mode = 'browser'

    def _browser_get(self, url):
        self._start_browser()
        js = """async ({url}) => {
          const r = await fetch(url, {
            credentials: 'include',
            cache: 'no-store',
            headers: {
              'Accept': 'application/json,text/plain,*/*',
              'x-api-version': '1.0',
              'X-Auth-Token': '',
              'X-Brand': '3',
              'X-IdCanale': '0'
            }
          });
          return {status: r.status, text: await r.text()};
        }"""
        last = None
        for attempt in range(2):
            result = self._page.evaluate(js, {'url': url})
            last = result
            status = int(result.get('status') or 0)
            if status == 200:
                return status, json.loads(result.get('text') or '{}')
            if status not in (401, 403, 429):
                raise RuntimeError(f'BetFlag browser API HTTP {status}: {(result.get("text") or "")[:300]}')
            self.blocked_statuses.append(status)
            if attempt == 0:
                try:
                    self._page.reload(wait_until='domcontentloaded', timeout=45000)
                    self._page.wait_for_timeout(3000)
                except Exception as e:
                    self.browser_errors.append(repr(e))
                time.sleep(1.0)
        raise RuntimeError(f'BetFlag browser recovery blocked HTTP {last.get("status") if last else None}')

    def get(self, url):
        if self.mode == 'browser':
            return self._browser_get(url)
        try:
            return self._http_get(url)
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403, 429):
                raise
            self.blocked_statuses.append(e.code)
            self.mode = 'browser'
            return self._browser_get(url)

    def diagnostics(self):
        return {
            'transport_mode': self.mode,
            'browser_recovery_used': self.browser_bootstraps > 0,
            'browser_bootstraps': self.browser_bootstraps,
            'blocked_statuses': self.blocked_statuses[-20:],
            'browser_errors': self.browser_errors[-10:],
        }

    def close(self):
        if self._context is not None:
            try:
                tmp = self.storage_state.with_suffix('.tmp')
                self._context.storage_state(path=str(tmp))
                tmp.replace(self.storage_state)
            except Exception as e:
                self.browser_errors.append(repr(e))
        for obj, method in ((self._context, 'close'), (self._browser, 'close')):
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._page = self._context = self._browser = self._pw = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
