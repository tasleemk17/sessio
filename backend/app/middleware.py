"""Two small ASGI middlewares: safe response headers, and a hard cap on request size."""

import json

from . import config

JSON_LIMIT = 64 * 1024  # every JSON body in this API is small


def _upload_limit() -> int:
    return config.MAX_FILE_MB * 1024 * 1024 + 64 * 1024  # the file plus multipart framing


class SecurityHeaders:
    """Adds headers that tell browsers not to sniff, frame or cache what the API returns."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = {k.lower(): v for k, v in message.get("headers", [])}
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"cross-origin-resource-policy": b"same-site",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                    # An API answer is never worth keeping in a shared cache: it can hold one person's data
                    b"cache-control": b"no-store",
                    # An API returns data, not pages: if one is ever opened as a page, it can load nothing
                    b"content-security-policy": b"default-src 'none'; frame-ancestors 'none'",
                }
                if config.PRODUCTION:
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                message["headers"] = list(message.get("headers", [])) + [(k, v) for k, v in extra.items() if k not in headers]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimit:
    """Refuses a request body that is too big, before it is stored in memory. It counts the bytes as they arrive,
    so it also stops a body sent in chunks with no Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_upload = scope["path"].endswith("/file")
        limit = _upload_limit() if is_upload else JSON_LIMIT
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            return await self._reject(send)

        seen = 0
        too_big = False

        async def counting_receive():
            nonlocal seen, too_big
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    too_big = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        started = False

        async def guarded_send(message):
            nonlocal started
            if too_big and not started:
                started = True
                return await self._reject(send)
            if too_big:
                return
            started = started or message["type"] == "http.response.start"
            await send(message)

        await self.app(scope, counting_receive, guarded_send)

    @staticmethod
    async def _reject(send):
        body = json.dumps({"detail": "That request is too large"}).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
