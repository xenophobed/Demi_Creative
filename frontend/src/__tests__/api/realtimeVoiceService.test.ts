/* @vitest-environment node */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import apiClient from '@/api/client'
import { realtimeVoiceService } from '@/api/services/realtimeVoiceService'

vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

describe('realtimeVoiceService.startSession (#616)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('POSTs to /me/agent/voice/session with the request shape', async () => {
    const response = {
      session_id: 'voice_sess_abc',
      ephemeral_token: 't'.repeat(32),
      expires_at: '2026-06-01T00:01:00Z',
      ws_url: '/api/v1/me/agent/voice/stream',
      provider_config: {
        provider: 'mock' as const,
        sample_rate_hz: 16000,
        audio_format: 'pcm16' as const,
      },
    }
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: response })

    const result = await realtimeVoiceService.startSession({
      child_id: 'child_xyz',
    })

    expect(result).toBe(response)
    expect(apiClient.post).toHaveBeenCalledWith('/me/agent/voice/session', {
      child_id: 'child_xyz',
    })
  })

  it('passes the optional persona field through unchanged', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        session_id: 's',
        ephemeral_token: 't'.repeat(32),
        expires_at: '2026-06-01T00:01:00Z',
        ws_url: '/ws',
        provider_config: {
          provider: 'hybrid',
          sample_rate_hz: 16000,
          audio_format: 'opus',
        },
      },
    })

    await realtimeVoiceService.startSession({
      child_id: 'child_xyz',
      persona: 'buddy_calm',
    })

    expect(apiClient.post).toHaveBeenCalledWith('/me/agent/voice/session', {
      child_id: 'child_xyz',
      persona: 'buddy_calm',
    })
  })

  it('surfaces the response.data unchanged (no envelope unwrapping)', async () => {
    const canned = { session_id: 'unique', ephemeral_token: 'x'.repeat(32), expires_at: '2026-06-01T00:01:00Z', ws_url: '/ws', provider_config: { provider: 'mock', sample_rate_hz: 16000, audio_format: 'pcm16' } }
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: canned })

    const out = await realtimeVoiceService.startSession({ child_id: 'c' })
    expect(out).toEqual(canned)
  })

  it('rejects when the underlying apiClient rejects', async () => {
    const err = new Error('501 not implemented')
    vi.mocked(apiClient.post).mockRejectedValueOnce(err)

    await expect(
      realtimeVoiceService.startSession({ child_id: 'c' }),
    ).rejects.toThrow('501 not implemented')
  })
})
