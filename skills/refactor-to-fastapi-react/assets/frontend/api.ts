// Single HTTP wrapper for the whole app. Components call `api.*` — never `fetch` directly —
// so the base path, error handling, and streaming live in one place. Same-origin '/api' works
// in dev (Vite proxy) and in single-origin production (served from the same server).
//
// This file is also where the backend contract becomes types: mirror each Pydantic response
// model as an interface (here or in `types.ts`) and annotate the wrapper that returns it. Then
// a renamed field is a compile error at `npm run build`, not a blank panel at runtime.

const BASE = '/api'

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

// `T` is the decoded JSON shape the caller expects — pass it explicitly in each endpoint
// wrapper below, so the contract lives here and not in every component.
async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers, signal } = opts
  const finalHeaders: Record<string, string> = { ...headers }
  const init: RequestInit = { method, signal }
  if (body instanceof FormData) {
    init.body = body // let the browser set the multipart boundary
  } else if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  init.headers = finalHeaders
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`)
  }
  return (res.status === 204 ? null : await res.json()) as T
}

// One member per SSE event the backend frames, so a consumer's `switch` is checked
// exhaustively instead of matching stringly-typed names. A union, not an `enum`: the Vite
// template compiles with `erasableSyntaxOnly`, under which `enum` is a hard error (TS1294).
export type StreamEvent =
  | { type: 'token'; data: { text: string } }
  | { type: 'done'; data: { finished: true } }
  | { type: 'error'; data: { message: string } }

const STREAM_EVENT_TYPES = ['token', 'done', 'error'] as const

// Guard at the wire boundary, so an unknown frame (a keepalive, a new backend event) is dropped
// instead of smuggled through as a well-typed lie — `JSON.parse` returns `any`, so a bare
// assertion would hand the consumer a value its exhaustive `switch` says cannot exist. Add the
// name here when you add it to StreamEvent.
function isStreamEventType(t: string): t is StreamEvent['type'] {
  return (STREAM_EVENT_TYPES as readonly string[]).includes(t)
}

// Mirrors the backend's Pydantic response model of the same name — one interface per model.
export type Status = { ready: boolean; version: string }

export const api = {
  // Plain JSON endpoints — the type argument mirrors the Pydantic response model. Keep at least
  // one real wrapper here: `noUnusedLocals` is on in the scaffold's tsconfig, so a file where
  // every endpoint is commented out fails the build with TS6133 on `request` itself.
  getStatus: () => request<Status>('/status'),
  //   createThing: (data: NewThing) => request<Thing>('/things', { method: 'POST', body: data }),

  // Streaming POST (tokens/answer). A browser EventSource can't POST, so we read the fetch
  // stream manually and parse SSE frames. `onEvent` fires once per framed event.
  async stream(
    path: string,
    body: unknown,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE permits CR, LF, or CRLF line endings; each frame ends with a blank line.
      let sep: number
      let separator: RegExpMatchArray | null
      while ((separator = buffer.match(/(?:\r\n|\r(?!\n)|\n){2}/)) !== null) {
        sep = separator.index ?? -1
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + separator[0].length)
        let type = 'message'
        const dataLines: string[] = []
        for (const line of frame.split(/\r\n|\r(?!\n)|\n/)) {
          if (line.startsWith('event:')) type = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
        }
        const data = dataLines.join('\n')
        // The wire is untyped; validate the discriminant once here, so callers stay checked.
        if (data && isStreamEventType(type)) {
          onEvent({ type, data: JSON.parse(data) } as StreamEvent)
          if (type === 'done' || type === 'error') {
            await reader.cancel()
            return
          }
        }
      }
    }
  },
}

// Streaming GET (progress) is simpler — use the native EventSource, since GET is allowed:
//   const es = new EventSource(`${BASE}/jobs/${id}/events`)
//   es.addEventListener('progress', (e: MessageEvent<string>) => {
//     const progress = JSON.parse(e.data) as Progress
//   })
//   es.addEventListener('done', () => es.close())
