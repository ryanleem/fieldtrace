"""Single-process demo limits; provider keys use the existing verified auth policy."""
import asyncio
import logging
from math import ceil
from collections import deque
from time import monotonic

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from app import auth

logger = logging.getLogger(__name__)


class DemoSafetyMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.requests, self.writes, self.providers = deque(), deque(), deque()
        self.provider_users = {}
        self.active = 0
        self.writing = False

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or self.settings.app_env != 'production':
            return await self.app(scope, receive, send)

        async def reject(status, message, retry_after=60):
            headers = {'Retry-After': str(retry_after)} if status == 429 else {}
            await JSONResponse({'detail': message}, status_code=status, headers=headers)(scope, receive, send)

        path = scope['path'].rstrip('/')
        write = scope['method'] not in {'GET', 'HEAD', 'OPTIONS'}
        provider = write and (path.endswith('/equipment/identify') or path.endswith('/analyze') or path.endswith('/troubleshooting/run')
                              or path.endswith('/troubleshooting/follow-up'))
        # Batch analysis could multiply one admitted action into dozens of calls.
        if path.endswith('/images/analyze-all') or path.startswith('/documents'):
            return await reject(403, 'This operation is unavailable in the public demo.')
        now = monotonic()
        budgets = [('requests', self.requests, 60, self.settings.demo_requests_per_minute)]
        if write:
            budgets.append(('writes', self.writes, 3600, self.settings.demo_writes_per_hour))
        for _, queue, window, limit in budgets:
            while queue and queue[0] <= now - window:
                queue.popleft()
        # Global counters intentionally ignore spoofable forwarding/client headers.
        if self.active >= 8 or (write and self.writing):
            logger.warning('Demo guard rejection reason=%s active=%d writing=%s',
                           'concurrency' if self.active >= 8 else 'concurrent_write', self.active, self.writing)
            return await reject(429, 'Demo is busy. Retry later.')
        async def check_budgets(entries, checked_at):
            exhausted = [(name, q, window, limit) for name, q, window, limit in entries if len(q) >= limit]
            if not exhausted:
                return False
            retry_after = max(max(1, ceil(q[len(q)-limit] + window - checked_at)) for _, q, window, limit in exhausted)
            for name, q, window, limit in exhausted:
                # No paths, session/user IDs, proxy headers, or credentials.
                logger.warning('Demo guard rejection reason=%s used=%d limit=%d window_seconds=%d retry_after=%d',
                               name, len(q), limit, window, retry_after)
            await reject(429, 'Demo request budget reached. Retry later.', retry_after)
            return True
        if path != '/health' and await check_budgets(budgets, now):
            return
        if path != '/health':
            for _, queue, _, _ in budgets:
                queue.append(now)
        self.active += 1
        if write:
            self.writing = True
        started = False
        dispatched = False
        response_status = None
        reservation = None

        async def tracked_send(message):
            nonlocal started, response_status
            if message['type'] == 'http.response.start':
                started = True
                response_status = message['status']
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
            if provider:
                # Body/request limits run first; invalid/public traffic cannot
                # reserve any paid-provider capacity. Never use proxy IPs or
                # session IDs, and never decode a token without verification.
                authorization = Request(scope).headers.get('authorization', '')
                scheme, _, token = authorization.partition(' ')
                if scheme.lower() != 'bearer' or not token:
                    return await reject(401, 'Sign in to continue.')
                try:
                    user = await run_in_threadpool(auth.verify_token, token, self.settings)
                except HTTPException as error:
                    return await reject(error.status_code, 'Sign in to continue.' if error.status_code == 401 else 'Authentication service unavailable.')
                scope['fieldtrace.verified_user'] = user
                admitted_at = monotonic()
                # Prune idle user buckets as well as active ones: memory is
                # bounded by users admitted within the global hourly ceiling.
                for key, queue in list(self.provider_users.items()):
                    while queue and queue[0] <= admitted_at - 3600:
                        queue.popleft()
                    if not queue:
                        del self.provider_users[key]
                while self.providers and self.providers[0] <= admitted_at - 3600:
                    self.providers.popleft()
                user_queue = self.provider_users.get(user, deque())
                provider_budgets = [
                    ('provider_actions_user', user_queue, 3600, self.settings.demo_provider_actions_per_user_per_hour),
                    ('provider_actions_global', self.providers, 3600, self.settings.demo_provider_actions_per_hour),
                ]
                if await check_budgets(provider_budgets, admitted_at):
                    return
                # No await between checking/reserving; the mutation guard also
                # serializes these operations within the single worker.
                self.provider_users[user] = user_queue
                user_queue.append(admitted_at)
                self.providers.append(admitted_at)
                reservation = (user, user_queue, admitted_at)
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}

            dispatched = True
            await self.app(scope, bounded_receive, tracked_send)
        except TimeoutError:
            if not started:
                await reject(408, 'Request timed out.')
        except Exception:
            # Do not return or log exception text: DB/provider exceptions may contain secrets.
            if not started:
                await reject(503, 'Service unavailable. Retry later.')
        finally:
            # Reserve provider capacity atomically, but do not charge body-level
            # rejection or auth/ownership denial as a provider action. Keep the
            # request/write budgets charged so invalid traffic remains limited.
            # Provider/unknown server failures still consume capacity.
            if reservation and (not dispatched or response_status in {401, 403, 404}):
                user, queue, admitted_at = reservation
                if admitted_at in self.providers:
                    self.providers.remove(admitted_at)
                if admitted_at in queue:
                    queue.remove(admitted_at)
                if not queue:
                    self.provider_users.pop(user, None)
            self.active -= 1
            if write:
                self.writing = False


def configure_safety(app, settings):
    app.add_middleware(DemoSafetyMiddleware, settings=settings)
    if settings.app_env == 'production':
        async def validation_error(request, exc):
            return JSONResponse({'detail': 'Invalid request. Check input types and limits.'}, status_code=422)

        async def http_error(request, exc):
            messages = {401: 'Sign in to continue.', 404: 'Resource not found.', 409: 'Session changed. Refresh and retry.',
                        422: 'Invalid request. Check input types and limits.', 403: 'Operation unavailable.'}
            return JSONResponse({'detail': messages.get(exc.status_code, 'Request could not be completed.')},
                                status_code=exc.status_code)

        app.add_exception_handler(RequestValidationError, validation_error)
        app.add_exception_handler(HTTPException, http_error)
