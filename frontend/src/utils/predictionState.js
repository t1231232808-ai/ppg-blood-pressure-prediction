import { reactive } from 'vue'

const state = reactive({
  latestResult: null
})

export function usePredictionState() {
  function setLatestResult(result) {
    state.latestResult = result
    sessionStorage.setItem('latest_prediction_result', JSON.stringify(result))
  }

  function getLatestResult() {
    if (state.latestResult) return state.latestResult
    const raw = sessionStorage.getItem('latest_prediction_result')
    if (!raw) return null
    try {
      state.latestResult = JSON.parse(raw)
      return state.latestResult
    } catch {
      return null
    }
  }

  return {
    state,
    setLatestResult,
    getLatestResult
  }
}
