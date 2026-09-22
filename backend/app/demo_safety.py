"""Single-process public-demo guard. This is deliberately NOT authentication."""
import asyncio
from collections import deque
from time import monotonic

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class DemoSafetyMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.requests, self.writes, self.providers = deque(), deque(), deque()
        self.active = 0
        self.writing = False

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or self.settings.app_env != 'production':
            return await self.app(scope, receive, send)

        async def reject(status, message):
            headers = {'Retry-After': '60'} if status == 429 else {}
            await JSONResponse({'detail': message}, status_code=status, headers=headers)(scope, receive, send)

        path = scope['path'].rstrip('/')
        write = scope['method'] not in {'GET', 'HEAD', 'OPTIONS'}
        provider = write and (path.endswith('/analyze') or path.endswith('/troubleshooting/run')
                              or path.endswith('/troubleshooting/follow-up'))
        # Batch analysis could multiply one admitted action into dozens of calls.
        if path.endswith('/images/analyze-all') or path.startswith('/documents'):
            return await reject(403, 'This operation is unavailable in the public demo.')
        now = monotonic()
        budgets = [(self.requests, 60, self.settings.demo_requests_per_minute)]
        if write:
            budgets.append((self.writes, 3600, self.settings.demo_writes_per_hour))
        if provider:
            budgets.append((self.providers, 3600, self.settings.demo_provider_actions_per_hour))
        for queue, window, limit in budgets:
            while queue and queue[0] <= now - window:
                queue.popleft()
        # Global counters intentionally ignore spoofable forwarding/client headers.
        if self.active >= 8 or (write and self.writing):
            return await reject(429, 'Demo is busy. Retry later.')
        if path != '/health' and any(len(q) >= limit for q, _, limit in budgets):
            return await reject(429, 'Demo request budget reached. Retry later.')
        if path != '/health':
            for queue, _, _ in budgets:
                queue.append(now)
        self.active += 1
        if write:
            self.writing = True
        started = False

        async def tracked_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            headers = dict(scope['headers'])
            limit = 12 * 1024 * 1024 if headers.get(b'content-type', b'').startswith(b'multipart/form-data') else 64 * 1024
            try:
                declared = int(headers.get(b'content-length', b'0'))
                if declared < 0:
                    raise ValueError
            except ValueError:
                return await reject(400, 'Invalid request length.')
            if declared > limit:
                return await reject(413, 'Request exceeds the demo size limit.')
            body = bytearray()
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    chunk = message.get('body', b'')
                    if len(body) + len(chunk) > limit:
                        return await reject(413, 'Request exceeds the demo size limit.')
                    body.extend(chunk)
                    if not message.get('more_body', False):
                        break
            if write and path.endswith('/images'):
                used = sum(p.stat().st_size for p in self.settings.uploads_dir.rglob('*') if p.is_file())
                if used + len(body) > self.settings.demo_upload_quota_bytes:
                    return await reject(507, 'Demo image storage budget reached.')
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}

            await self.app(scope, bounded_receive, tracked_send)
        except TimeoutError:
            if not started:
                await reject(408, 'Request timed out.')
        except Exception:
            # Do not return or log exception text: DB/provider exceptions may contain secrets.
            if not started:
                await reject(503, 'Service unavailable. Retry later.')
        finally:
            self.active -= 1
            if write:
                self.writing = False


def configure_safety(app, settings):
    app.add_middleware(DemoSafetyMiddleware, settings=settings)
    if settings.app_env == 'production':
        async def validation_error(request, exc):
            return JSONResponse({'detail': 'Invalid request. Check input types and limits.'}, status_code=422)

        async def http_error(request, exc):
            messages = {404: 'Resource not found.', 409: 'Session changed. Refresh and retry.',
                        422: 'Invalid request. Check input types and limits.', 403: 'Operation unavailable.'}
            return JSONResponse({'detail': messages.get(exc.status_code, 'Request could not be completed.')},
                                status_code=exc.status_code)

        app.add_exception_handler(RequestValidationError, validation_error)
        app.add_exception_handler(HTTPException, http_error)
