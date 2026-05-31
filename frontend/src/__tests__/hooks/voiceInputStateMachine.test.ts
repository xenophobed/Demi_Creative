import { describe, expect, it } from 'vitest'
import {
  isBusyState,
  voiceReducer,
  type VoiceInputEvent,
  type VoiceInputState,
} from '@/hooks/voiceInputStateMachine'

const START_WITH_CONSENT: VoiceInputEvent = { type: 'start', consentGranted: true }
const START_WITHOUT_CONSENT: VoiceInputEvent = { type: 'start', consentGranted: false }

describe('voiceReducer: idle/start transitions', () => {
  it('start without consent → consent-required', () => {
    expect(voiceReducer('idle', START_WITHOUT_CONSENT)).toBe('consent-required')
  })

  it('start with consent → requesting', () => {
    expect(voiceReducer('idle', START_WITH_CONSENT)).toBe('requesting')
  })

  it('start from done re-enters the flow', () => {
    expect(voiceReducer('done', START_WITH_CONSENT)).toBe('requesting')
  })

  it('start from rejected re-enters the flow', () => {
    expect(voiceReducer('rejected', START_WITH_CONSENT)).toBe('requesting')
  })

  it('start from error re-enters the flow', () => {
    expect(voiceReducer('error', START_WITH_CONSENT)).toBe('requesting')
  })

  it('start during recording is a no-op (already busy)', () => {
    expect(voiceReducer('recording', START_WITH_CONSENT)).toBe('recording')
  })
})

describe('voiceReducer: consent gate', () => {
  it('consentGranted on consent-required → requesting', () => {
    expect(voiceReducer('consent-required', { type: 'consentGranted' })).toBe('requesting')
  })

  it('consentDismissed → idle', () => {
    expect(voiceReducer('consent-required', { type: 'consentDismissed' })).toBe('idle')
  })

  it('consentGranted from wrong state is a no-op', () => {
    expect(voiceReducer('idle', { type: 'consentGranted' })).toBe('idle')
  })
})

describe('voiceReducer: stream lifecycle', () => {
  it('streamReady on requesting → recording', () => {
    expect(voiceReducer('requesting', { type: 'streamReady' })).toBe('recording')
  })

  it('streamError on requesting → error', () => {
    expect(voiceReducer('requesting', { type: 'streamError' })).toBe('error')
  })

  it('stopRecording → processing', () => {
    expect(voiceReducer('recording', { type: 'stopRecording' })).toBe('processing')
  })

  it('stopRecording on idle is a no-op', () => {
    expect(voiceReducer('idle', { type: 'stopRecording' })).toBe('idle')
  })
})

describe('voiceReducer: transcription outcomes', () => {
  it('transcriptionPassed → done', () => {
    expect(voiceReducer('processing', { type: 'transcriptionPassed' })).toBe('done')
  })

  it('transcriptionRejected → rejected (safety failed)', () => {
    expect(voiceReducer('processing', { type: 'transcriptionRejected' })).toBe('rejected')
  })

  it('transcriptionError → error', () => {
    expect(voiceReducer('processing', { type: 'transcriptionError' })).toBe('error')
  })

  it('transcriptionPassed from other states is a no-op', () => {
    expect(voiceReducer('recording', { type: 'transcriptionPassed' })).toBe('recording')
  })
})

describe('voiceReducer: reset + unsupported', () => {
  it('reset → idle from any state', () => {
    const states: VoiceInputState[] = [
      'recording', 'processing', 'done', 'rejected', 'error', 'consent-required',
    ]
    for (const s of states) {
      expect(voiceReducer(s, { type: 'reset' })).toBe('idle')
    }
  })

  it('unsupported is terminal', () => {
    const events: VoiceInputEvent[] = [
      START_WITH_CONSENT, { type: 'streamReady' }, { type: 'reset' },
      { type: 'transcriptionPassed' },
    ]
    for (const e of events) {
      expect(voiceReducer('unsupported', e)).toBe('unsupported')
    }
  })
})

describe('isBusyState', () => {
  it('returns true only when the hook owns hardware or the server', () => {
    expect(isBusyState('requesting')).toBe(true)
    expect(isBusyState('recording')).toBe(true)
    expect(isBusyState('processing')).toBe(true)
    expect(isBusyState('idle')).toBe(false)
    expect(isBusyState('done')).toBe(false)
    expect(isBusyState('rejected')).toBe(false)
    expect(isBusyState('error')).toBe(false)
  })
})
