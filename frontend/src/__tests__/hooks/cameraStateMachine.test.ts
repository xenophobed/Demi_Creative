import { describe, expect, it } from 'vitest'
import {
  cameraReducer,
  isActiveStreamState,
  type CameraEvent,
  type CameraState,
} from '@/hooks/cameraStateMachine'

const START_WITH_CONSENT: CameraEvent = { type: 'start', consentGranted: true }
const START_WITHOUT_CONSENT: CameraEvent = { type: 'start', consentGranted: false }
const STREAM_READY: CameraEvent = { type: 'streamReady' }
const STREAM_ERROR: CameraEvent = { type: 'streamError', errorKind: 'permission_denied' }

describe('cameraReducer: idle transitions', () => {
  it('start without consent → consent-required', () => {
    expect(cameraReducer('idle', START_WITHOUT_CONSENT)).toBe('consent-required')
  })

  it('start with consent → requesting', () => {
    expect(cameraReducer('idle', START_WITH_CONSENT)).toBe('requesting')
  })

  it('markUnsupported from idle → unsupported', () => {
    expect(cameraReducer('idle', { type: 'markUnsupported' })).toBe('unsupported')
  })

  it('streamReady on idle is a no-op', () => {
    expect(cameraReducer('idle', STREAM_READY)).toBe('idle')
  })
})

describe('cameraReducer: consent gate', () => {
  it('consentGranted → requesting', () => {
    expect(cameraReducer('consent-required', { type: 'consentGranted' })).toBe('requesting')
  })

  it('consentDismissed → idle', () => {
    expect(cameraReducer('consent-required', { type: 'consentDismissed' })).toBe('idle')
  })

  it('consentGranted from idle is a no-op (wrong stage)', () => {
    expect(cameraReducer('idle', { type: 'consentGranted' })).toBe('idle')
  })
})

describe('cameraReducer: stream lifecycle', () => {
  it('streamReady on requesting → live', () => {
    expect(cameraReducer('requesting', STREAM_READY)).toBe('live')
  })

  it('streamError on requesting → error', () => {
    expect(cameraReducer('requesting', STREAM_ERROR)).toBe('error')
  })

  it('capture on live → captured', () => {
    expect(cameraReducer('live', { type: 'capture' })).toBe('captured')
  })

  it('capture on idle is a no-op', () => {
    expect(cameraReducer('idle', { type: 'capture' })).toBe('idle')
  })
})

describe('cameraReducer: post-capture transitions', () => {
  it('retake → requesting (restarts stream)', () => {
    expect(cameraReducer('captured', { type: 'retake' })).toBe('requesting')
  })

  it('confirm → idle (consumer keeps the blob)', () => {
    expect(cameraReducer('captured', { type: 'confirm' })).toBe('idle')
  })
})

describe('cameraReducer: toggle/retry/stop', () => {
  it('toggleFacing on live restarts the stream', () => {
    expect(cameraReducer('live', { type: 'toggleFacing' })).toBe('requesting')
  })

  it('toggleFacing on captured restarts the stream', () => {
    expect(cameraReducer('captured', { type: 'toggleFacing' })).toBe('requesting')
  })

  it('toggleFacing on idle is a no-op', () => {
    expect(cameraReducer('idle', { type: 'toggleFacing' })).toBe('idle')
  })

  it('retry from error → requesting', () => {
    expect(cameraReducer('error', { type: 'retry' })).toBe('requesting')
  })

  it('retry from idle is a no-op', () => {
    expect(cameraReducer('idle', { type: 'retry' })).toBe('idle')
  })

  it('stop from any state → idle', () => {
    const states: CameraState[] = ['requesting', 'live', 'captured', 'error', 'consent-required']
    for (const s of states) {
      expect(cameraReducer(s, { type: 'stop' })).toBe('idle')
    }
  })
})

describe('cameraReducer: unsupported is terminal', () => {
  it('rejects every event once in unsupported', () => {
    const events: CameraEvent[] = [
      START_WITH_CONSENT,
      START_WITHOUT_CONSENT,
      STREAM_READY,
      STREAM_ERROR,
      { type: 'capture' },
      { type: 'retake' },
      { type: 'confirm' },
      { type: 'toggleFacing' },
      { type: 'retry' },
      { type: 'stop' },
      { type: 'consentGranted' },
      { type: 'consentDismissed' },
    ]
    for (const e of events) {
      expect(cameraReducer('unsupported', e)).toBe('unsupported')
    }
  })
})

describe('isActiveStreamState', () => {
  it('returns true only while the camera owns the device', () => {
    expect(isActiveStreamState('requesting')).toBe(true)
    expect(isActiveStreamState('live')).toBe(true)
    expect(isActiveStreamState('idle')).toBe(false)
    expect(isActiveStreamState('captured')).toBe(false)
    expect(isActiveStreamState('error')).toBe(false)
    expect(isActiveStreamState('consent-required')).toBe(false)
    expect(isActiveStreamState('unsupported')).toBe(false)
  })
})
