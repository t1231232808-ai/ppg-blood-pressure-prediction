export function firstSimilarSignal(result) {
  const sample = (result?.similar_samples || []).find((item) => Array.isArray(item.signal) && item.signal.length)
  if (sample) return sample.signal
  const waveforms = result?.similar_waveforms || []
  return waveforms[0]?.signal || []
}

export function autoSavedButtonText(result) {
  return result?.record_id ? '已自动保存' : '保存状态确认中'
}
