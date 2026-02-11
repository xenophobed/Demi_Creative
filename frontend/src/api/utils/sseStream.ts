import type { StreamCallbacks, SSEEventType } from '@/types/api'

/**
 * Read an SSE stream from a fetch Response and dispatch events to callbacks.
 */
export async function consumeSSEStream(
  response: Response,
  callbacks: StreamCallbacks
): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let eventType: SSEEventType | null = null

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim() as SSEEventType
        } else if (line.startsWith('data: ') && eventType) {
          const data = JSON.parse(line.slice(6))

          switch (eventType) {
            case 'status':      callbacks.onStatus?.(data);     break
            case 'thinking':    callbacks.onThinking?.(data);   break
            case 'tool_use':    callbacks.onToolUse?.(data);    break
            case 'tool_result': callbacks.onToolResult?.(data); break
            case 'session':     callbacks.onSession?.(data);    break
            case 'result':      callbacks.onResult?.(data);     break
            case 'complete':    callbacks.onComplete?.(data);   break
            case 'error':       callbacks.onError?.(data);      break
          }
          eventType = null
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
