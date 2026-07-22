# Streaming over SSE — the two flows and the trap

Server-Sent Events (SSE) is the right tool for "stream tokens as they generate" and "push
progress updates" — it's one-way server→client, works over plain HTTP, and is far simpler than
WebSockets. There are two distinct flows, and the POST one has a trap that will freeze your
whole server if you get it wrong.

## Flow A — streaming a POST response (tokens / answers)

The browser's native `EventSource` can only issue **GET** requests, but a chat/answer endpoint
usually needs a **POST** (the prompt + params are in the body). So on the frontend you don't
use `EventSource` — you read the `fetch` response stream manually and parse SSE frames yourself
(`assets/frontend/api.ts` has a ready typed `stream()` reader).

On the **server**, the trap: most LLM/DB SDK calls are **blocking** (synchronous). If you write
an `async def` generator and make a blocking call inside it, you block the event loop — and
since one event loop serves *every* connection, the entire server freezes until that call
returns. Nobody else can even load a page.

The fix is a **synchronous generator** returned via Starlette's `StreamingResponse`. Starlette
detects a sync generator and runs it in a **threadpool**, so the blocking call happens off the
event loop and the server stays responsive:

```python
from starlette.responses import StreamingResponse

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

@router.post("/chat")
def chat(req: ChatRequest, engine=Depends(get_engine)):
    def gen():                      # SYNC generator -> threadpool -> safe for blocking calls
        yield _sse("sources", {...})
        for token in engine.stream_answer(req.prompt):   # blocking is fine here
            yield _sse("token", {"text": token})
        yield _sse("done", {"stats": {...}})
    return StreamingResponse(gen(), media_type="text/event-stream")
```

Note `def chat`, not `async def` — let FastAPI run the endpoint itself in the threadpool too.

## Flow B — streaming progress on a GET (jobs / ingest)

For progress you *can* use `EventSource`, because polling a job's status is a natural GET. Here
an **async** generator is appropriate (you're `await asyncio.sleep`-ing between polls, not
making one long blocking call). `sse_starlette.EventSourceResponse` handles framing and
client-disconnect cleanup:

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, registry=Depends(get_registry)):
    async def gen():
        while True:
            snap = registry.snapshot(job_id)
            yield {"event": "progress", "data": json.dumps(snap)}
            if snap["state"] in ("done", "error", "cancelled"):
                yield {"event": "done", "data": "{}"}
                return
            await asyncio.sleep(0.3)
    return EventSourceResponse(gen())
```

Frontend: `new EventSource('/api/jobs/<id>/events')`, listen for `progress` and `done`.

## Framing rules that avoid off-by-one bugs
- Each frame: an `event:` line, one or more `data:` lines, then a **blank line**. JSON goes in
  `data:`.
- On the client, only treat the stream as finished **after reading the terminal event's
  `data:`** — a common bug is breaking the loop on seeing `event: done` before consuming its
  payload, which drops the final stats.
- Always send a terminal `done` (and a distinct `error`) event so the client knows to stop and
  can distinguish clean completion from a dropped connection.
