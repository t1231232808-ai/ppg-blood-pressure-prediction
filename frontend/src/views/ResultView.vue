<template>
  <div class="result-page">
    <AppTopNav active="result" />

    <main class="result-main">
      <h1 class="result-title">预测结果</h1>

      <template v-if="result">
        <el-card class="result-card" shadow="always">
          <template #header>
            <span>血压预测结果</span>
          </template>

          <div class="bp-result-grid">
            <div class="bp-item">
              <div class="bp-label">收缩压</div>
              <div class="bp-value">{{ result.sbp }}</div>
              <div class="bp-unit">mmHg</div>
              <el-tag :type="bpLevel.type">{{ bpLevel.label }}</el-tag>
            </div>
            <div class="bp-item">
              <div class="bp-label">舒张压</div>
              <div class="bp-value">{{ result.dbp }}</div>
              <div class="bp-unit">mmHg</div>
              <el-tag :type="bpLevel.type">{{ bpLevel.label }}</el-tag>
            </div>
          </div>

          <div class="confidence-row">
            <el-progress
              class="confidence-progress"
              :percentage="confidencePercent"
              :color="progressColors"
            />
            <span>置信度: {{ confidencePercent }}%</span>
          </div>

          <div class="predict-time">预测时间: {{ predictionTime }}</div>

          <el-alert
            v-if="result.is_low_confidence"
            class="low-confidence-alert"
            type="warning"
            :closable="false"
            :title="`预测置信度低于阈值 ${Math.round(Number(result.confidence_threshold) * 100)}%，建议重新采集或多次测量。`"
          />
        </el-card>

        <el-card class="result-card" shadow="always">
          <template #header>
            <span>PPG 波形对比</span>
          </template>
          <div ref="chartRef" class="comparison-chart"></div>
        </el-card>

        <el-card class="result-card" shadow="always">
          <template #header>
            <span>预测依据</span>
          </template>
          <p class="explanation-text">{{ result.explanation }}</p>
          <el-table :data="similarSamples" stripe>
            <el-table-column label="排名" width="90">
              <template #default="{ $index }">
                <strong v-if="$index === 0">#{{ $index + 1 }}</strong>
                <span v-else>#{{ $index + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="血压" width="160">
              <template #default="{ row }">{{ row.sbp }}/{{ row.dbp }} mmHg</template>
            </el-table-column>
            <el-table-column label="向量距离" width="160">
              <template #default="{ row }">{{ Number(row.distance).toFixed(4) }}</template>
            </el-table-column>
            <el-table-column label="数据来源">
              <template #default="{ row }">{{ row.source || '模拟数据' }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <div class="result-actions">
          <el-button plain @click="router.push('/prediction')">重新预测</el-button>
          <el-button type="success" @click="ElMessage.success('预测结果已自动保存，可查看本次详情或历史记录')">已自动保存</el-button>
          <el-button v-if="result.record_id" type="primary" @click="router.push(`/prediction/${result.record_id}`)">查看本次详情</el-button>
          <el-button plain @click="router.push('/records')">查看历史记录</el-button>
        </div>
      </template>

      <el-card v-else class="result-card" shadow="always">
        <el-empty description="未找到预测数据，请先上传 PPG 信号">
          <el-button type="primary" @click="router.push('/prediction')">去上传</el-button>
        </el-empty>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import client from '../api/client'
import AppTopNav from '../components/AppTopNav.vue'
import { usePredictionState } from '../utils/predictionState'
import { firstSimilarSignal } from '../utils/resultHelpers'

const router = useRouter()
const { getLatestResult, setLatestResult } = usePredictionState()
const result = ref(null)
const chartRef = ref(null)
let chart = null

const progressColors = [
  { color: '#F56C6C', percentage: 50 },
  { color: '#E6A23C', percentage: 75 },
  { color: '#67C23A', percentage: 100 }
]

const confidencePercent = computed(() => Math.round(Number(result.value?.confidence || 0) * 100))

const bpLevel = computed(() => {
  const sbp = Number(result.value?.sbp)
  const dbp = Number(result.value?.dbp)
  if (sbp >= 140 || dbp >= 90) return { label: '高血压', type: 'danger' }
  if (sbp >= 120 || dbp >= 80) return { label: '偏高', type: 'warning' }
  return { label: '正常', type: 'success' }
})

const similarSamples = computed(() => (result.value?.similar_samples || []).slice(0, 5))

const firstSimilarWaveform = computed(() => {
  return firstSimilarSignal(result.value)
})

const predictionTime = computed(() => {
  const value = result.value?.created_at || result.value?.prediction_time || new Date().toISOString()
  return String(value).replace('T', ' ').slice(0, 19)
})

function renderChart() {
  if (!chartRef.value) return
  const currentSignal = result.value?.raw_signal || result.value?.ppg_signal || []
  const similarSignal = firstSimilarWaveform.value
  const timeLabels = currentSignal.map((_, index) => (index / 125).toFixed(3))
  const series = [
    {
      name: '当前波形',
      type: 'line',
      data: currentSignal,
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#409EFF', width: 2 }
    }
  ]
  if (similarSignal.length) {
    series.push({
      name: '最相似历史波形',
      type: 'line',
      data: similarSignal,
      smooth: true,
      showSymbol: false,
      lineStyle: { color: '#E6A23C', type: 'dashed', width: 2 }
    })
  }

  chart = chart || echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: series.map((item) => item.name) },
    grid: { left: 45, right: 24, top: 50, bottom: 40 },
    xAxis: { type: 'category', name: '时间(s)', data: timeLabels },
    yAxis: { type: 'value', name: '幅值', min: 0, max: 1 },
    series
  })
}

async function hydrateResult() {
  const cached = getLatestResult()
  if (!cached) return
  result.value = cached

  if (cached.record_id) {
    try {
      const response = await client.get(`/prediction/${cached.record_id}`)
      result.value = { ...cached, ...response.data.data }
      setLatestResult(result.value)
    } catch {
      result.value = cached
    }
    await hydrateSimilarWaveforms(cached.record_id)
  }

  await nextTick()
  renderChart()
}

async function hydrateSimilarWaveforms(recordId) {
  try {
    const response = await client.get(`/prediction/${recordId}/similar`)
    result.value = {
      ...result.value,
      similar_samples: response.data.data.similar_samples || result.value.similar_samples || [],
      similar_waveforms: response.data.data.similar_waveforms || []
    }
    setLatestResult(result.value)
  } catch {
    ElMessage.warning('相似波形加载失败，仅展示当前波形')
  }
}

onMounted(hydrateResult)

onUnmounted(() => {
  if (chart) chart.dispose()
})
</script>

<style>
.result-page {
  min-height: 100vh;
  background: #f5f8fc;
}

.result-main {
  max-width: 1000px;
  margin: 0 auto;
  padding: 30px 16px;
}

.result-title {
  margin: 0 0 20px;
  color: #1f2937;
  font-size: 26px;
  font-weight: 700;
}

.result-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.bp-result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.bp-item {
  text-align: center;
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.bp-label {
  color: #6b7280;
  font-size: 15px;
}

.bp-value {
  margin-top: 10px;
  color: #111827;
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
}

.bp-unit {
  margin: 8px 0 12px;
  color: #9ca3af;
  font-size: 14px;
}

.confidence-row {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 24px;
}

.confidence-progress {
  flex: 1;
}

.predict-time {
  margin-top: 12px;
  color: #9ca3af;
  font-size: 13px;
}

.low-confidence-alert {
  margin-top: 18px;
}

.comparison-chart {
  height: 350px;
}

.explanation-text {
  margin: 0 0 16px;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.6;
}

.result-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin: 8px 0 24px;
}

@media (max-width: 720px) {
  .bp-result-grid {
    grid-template-columns: 1fr;
  }

  .confidence-row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
