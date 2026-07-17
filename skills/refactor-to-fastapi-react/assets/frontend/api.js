// Single HTTP wrapper for the whole app. Components call `api.*` — never `fetch` directly —
// so the base path, error handling, and streaming live in one place. Same-origin '/api' works
// in dev (Vite proxy) and in single-origin production (served from the same server).

const BASE = '/api'

async function request(path, { method = 'GET', body, headers } = {}) {
  const opts = { method, headers: { ...headers } }
  if (body instanceof FormData) {
    opts.body = body // let the browser set the multipart boundary
  } else if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`)
  }
  return res.status === 204 ? null : res.json()
}

export const api = {
  // Plain JSON endpoints:
  //   getStatus: () => request('/status'),
  //   createThing: (data) => request('/things', { method: 'POST', body: data }),

  // Streaming POST (tokens/answer). A browser EventSource can't POST, so we read the fetch
  // stream manually and parse SSE frames. `onEvent(type, data)` fires per framed event.
  async stream(path, body, onEvent, signal) {
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
      // SSE frames are separated by a blank line; each frame has `event:` and `data:` lines.
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        let type = 'message'
        let data = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) type = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (data) onEvent(type, JSON.parse(data))
      }
    }
  },
}

// Streaming GET (progress) is simpler — use the native EventSource, since GET is allowed:
//   const es = new EventSource(`${BASE}/jobs/${id}/events`)
//   es.addEventListener('progress', (e) => { ... JSON.parse(e.data) ... })
//   es.addEventListener('done', () => es.close())
