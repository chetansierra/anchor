// Minimal SSE-over-POST reader.
//
// EventSource can't POST or set a JSON body, so we stream the response with
// fetch + ReadableStream and parse `event:` / `data:` frames ourselves. Each
// complete frame (terminated by a blank line) is dispatched to `onFrame`.

export interface SSEFrame {
  event: string;
  data: unknown;
}

export interface StreamOptions {
  signal?: AbortSignal;
  onFrame: (frame: SSEFrame) => void;
}

export async function streamSSE(
  url: string,
  body: unknown,
  opts: StreamOptions,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch {
      /* non-JSON error body — keep the status message */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    // Frames are separated by a blank line ("\n\n").
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const rawFrame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const frame = parseFrame(rawFrame);
      if (frame) opts.onFrame(frame);
    }
  }
}

function parseFrame(raw: string): SSEFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  let data: unknown = dataLines.join("\n");
  try {
    data = JSON.parse(data as string);
  } catch {
    /* leave as string */
  }
  return { event, data };
}
