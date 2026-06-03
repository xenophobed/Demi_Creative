import { describe, expect, it } from 'vitest'
import {
  isActiveSessionState,
  TERMINAL_STATES,
  voiceConversationReducer,
  type VoiceConversationEvent,
  type VoiceConversationState,
} from '@/hooks/voiceConversationStateMachine'

const START_WITH_CONSENT: VoiceConversationEvent = {
  type: 'start',
  consentGranted: true,
}
const START_WITHOUT_CONSENT: VoiceConversationEvent = {
  type: 'start',
  consentGranted: false,
}

describe('voiceConversationReducer: idle entry', () => {
  it('start with consent → connecting', () => {
    expect(voiceConversationReducer('idle', START_WITH_CONSENT)).toBe('connecting')
  })

  it('start without consent stays idle (consent gate is the parent surface)', () => {
    expect(voiceConversationReducer('idle', START_WITHOUT_CONSENT)).toBe('idle')
  })

  it('markUnsupported from idle → unsupported', () => {
    expect(voiceConversationReducer('idle', { type: 'markUnsupported' })).toBe('unsupported')
  })

  it('events that do not match idle handlers are no-ops', () => {
    expect(voiceConversationReducer('idle', { type: 'sttPartial' })).toBe('idle')
    expect(voiceConversationReducer('idle', { type: 'wsOpen' })).toBe('idle')
  })

  it('endRequested from idle stays idle (no active session to end)', () => {
    expect(voiceConversationReducer('idle', { type: 'endRequested' })).toBe('idle')
  })
})

describe('voiceConversationReducer: connecting → listening', () => {
  it('tokenReceived stays connecting (WS still opening)', () => {
    expect(voiceConversationReducer('connecting', { type: 'tokenReceived' })).toBe('connecting')
  })

  it('wsOpen → listening', () => {
    expect(voiceConversationReducer('connecting', { type: 'wsOpen' })).toBe('listening')
  })

  it('streamError during connect → error', () => {
    expect(voiceConversationReducer('connecting', { type: 'streamError' })).toBe('error')
  })

  it('wsClose during connect → error (handshake never completed)', () => {
    expect(voiceConversationReducer('connecting', { type: 'wsClose' })).toBe('error')
  })
})

describe('voiceConversationReducer: listening', () => {
  it('sttPartial keeps listening', () => {
    expect(voiceConversationReducer('listening', { type: 'sttPartial' })).toBe('listening')
  })

  it('sttFinal → thinking', () => {
    expect(voiceConversationReducer('listening', { type: 'sttFinal' })).toBe('thinking')
  })

  it('streamError → error', () => {
    expect(voiceConversationReducer('listening', { type: 'streamError' })).toBe('error')
  })
})

describe('voiceConversationReducer: thinking → speaking', () => {
  it('assistantTextDelta stays thinking', () => {
    expect(voiceConversationReducer('thinking', { type: 'assistantTextDelta' })).toBe('thinking')
  })

  it('ttsStart → speaking', () => {
    expect(voiceConversationReducer('thinking', { type: 'ttsStart' })).toBe('speaking')
  })

  it('streamError from thinking → error', () => {
    expect(voiceConversationReducer('thinking', { type: 'streamError' })).toBe('error')
  })
})

describe('voiceConversationReducer: speaking + barge-in', () => {
  it('ttsEnd → listening', () => {
    expect(voiceConversationReducer('speaking', { type: 'ttsEnd' })).toBe('listening')
  })

  it('bargeIn → interrupted', () => {
    expect(voiceConversationReducer('speaking', { type: 'bargeIn' })).toBe('interrupted')
  })

  it('interrupted then sttPartial → listening', () => {
    expect(voiceConversationReducer('interrupted', { type: 'sttPartial' })).toBe('listening')
  })

  it('interrupted then wsOpen → listening (server ack received)', () => {
    expect(voiceConversationReducer('interrupted', { type: 'wsOpen' })).toBe('listening')
  })

  it('interrupted then streamError → error', () => {
    expect(voiceConversationReducer('interrupted', { type: 'streamError' })).toBe('error')
  })
})

describe('voiceConversationReducer: user-pressed-End is universal', () => {
  it('endRequested from every active state → ending', () => {
    const states: VoiceConversationState[] = [
      'connecting',
      'listening',
      'thinking',
      'speaking',
      'interrupted',
    ]
    for (const s of states) {
      expect(voiceConversationReducer(s, { type: 'endRequested' })).toBe('ending')
    }
  })

  it('ending waits for wsClose then → idle', () => {
    expect(voiceConversationReducer('ending', { type: 'wsClose' })).toBe('idle')
  })

  it('ending absorbs late streamError (we are already shutting down)', () => {
    expect(voiceConversationReducer('ending', { type: 'streamError' })).toBe('ending')
  })

  it('endRequested from idle stays idle (nothing to end)', () => {
    expect(voiceConversationReducer('idle', { type: 'endRequested' })).toBe('idle')
  })
})

describe('voiceConversationReducer: error + reset + unsupported', () => {
  it('error absorbs additional events until reset', () => {
    expect(voiceConversationReducer('error', { type: 'sttPartial' })).toBe('error')
    expect(voiceConversationReducer('error', { type: 'wsOpen' })).toBe('error')
  })

  it('reset returns any state to idle', () => {
    const states: VoiceConversationState[] = [
      'connecting',
      'listening',
      'thinking',
      'speaking',
      'interrupted',
      'ending',
      'error',
    ]
    for (const s of states) {
      expect(voiceConversationReducer(s, { type: 'reset' })).toBe('idle')
    }
  })

  it('unsupported absorbs every event (terminal)', () => {
    const events: VoiceConversationEvent[] = [
      START_WITH_CONSENT,
      { type: 'wsOpen' },
      { type: 'sttFinal' },
      { type: 'ttsStart' },
      { type: 'bargeIn' },
      { type: 'endRequested' },
      { type: 'streamError' },
      { type: 'reset' },
    ]
    for (const e of events) {
      expect(voiceConversationReducer('unsupported', e)).toBe('unsupported')
    }
  })

  it('TERMINAL_STATES contains unsupported only', () => {
    expect(TERMINAL_STATES.size).toBe(1)
    expect(TERMINAL_STATES.has('unsupported')).toBe(true)
  })
})

describe('isActiveSessionState', () => {
  it('returns true only while a real session exists', () => {
    expect(isActiveSessionState('connecting')).toBe(true)
    expect(isActiveSessionState('listening')).toBe(true)
    expect(isActiveSessionState('thinking')).toBe(true)
    expect(isActiveSessionState('speaking')).toBe(true)
    expect(isActiveSessionState('interrupted')).toBe(true)
    expect(isActiveSessionState('ending')).toBe(true)
  })

  it('returns false for idle / error / unsupported', () => {
    expect(isActiveSessionState('idle')).toBe(false)
    expect(isActiveSessionState('error')).toBe(false)
    expect(isActiveSessionState('unsupported')).toBe(false)
  })
})
