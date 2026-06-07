import { describe, expect, it } from 'vitest'
import { autoSavedButtonText, firstSimilarSignal } from './resultHelpers'

describe('result helpers', () => {
  it('uses signal from similar_samples first', () => {
    expect(firstSimilarSignal({ similar_samples: [{ signal: [0.1, 0.2] }], similar_waveforms: [{ signal: [0.3] }] })).toEqual([0.1, 0.2])
  })

  it('falls back to similar_waveforms', () => {
    expect(firstSimilarSignal({ similar_samples: [], similar_waveforms: [{ signal: [0.3, 0.4] }] })).toEqual([0.3, 0.4])
  })

  it('shows auto saved text when record id exists', () => {
    expect(autoSavedButtonText({ record_id: 1 })).toBe('已自动保存')
  })
})
