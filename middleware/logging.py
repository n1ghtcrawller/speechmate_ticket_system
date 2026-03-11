import time
from fastapi import Request
from starlette.responses import StreamingResponse
from starlette.requests import ClientDisconnect

async def log_requests(request: Request, call_next):
    start_time = time.time()

    try:
        print(f"\n📥 {request.method} {request.url}")
    except ClientDisconnect:
        print("⚠️ Клиент отключился до того, как запрос был обработан")
        return await call_next(request)

    response = await call_next(request)

    # Перехватываем тело ответа
    if hasattr(response, "body_iterator"):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        response = StreamingResponse(
            iter([body]),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=response.background,
        )
    else:
        body = getattr(response, "body", b"")

    process_time = time.time() - start_time
    body_preview = body.decode("utf-8", errors="ignore")[:500]  # первые 500 символов

    print(f"📤 {response.status_code} | {process_time:.3f}s")
    print(f"Ответ: {body_preview}\n")

    return response