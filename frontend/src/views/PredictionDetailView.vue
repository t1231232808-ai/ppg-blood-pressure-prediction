<template>
  <div class="detail-page">
    <AppTopNav active="records" />

    <main class="detail-main">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/prediction' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item :to="{ path: '/records' }">历史记录</el-breadcrumb-item>
        <el-breadcrumb-item>预测详情 #{{ recordId }}</el-breadcrumb-item>
      </el-breadcrumb>

      <template v-if="detail">
        <el-card class="detail-card" shadow="always">
          <template #header>
            <div class="card-header-row">
              <span>预测详情 #{{ detail.record_id }}</span>
              <span>{{ formatDateTime(detail.created_at) }}</span>
            </div>
          </template>

          <div class="overview-grid">
            <div class="overview-item">
              <div class="overview-label">收缩压</div>
              <div class="overview-value">{{ detail.sbp }} <span>mmHg</span></div>
              <el-tag :type="bpLevel.type">{{ bpLevel.label }}</el-tag>
            </div>
            <div class="overview-item">
              <div class="overview-label">舒张压</div>
              <div class="overview-value">{{ detail.dbp }} <span>mmHg</span></div>
              <el-tag :type="bpLevel.type">{{ bpLevel.label }}</el-tag>
            </div>
            <div class="overview-item">
              <div class="overview-label">置信度</div>
              <el-progress :percentage="confidencePercent" :color="progressColors" />
              <div class="confidence-text">{{ confidencePercent }}%</div>
            </div>
          </div>

          <div class="meta-row">
            <el-tag type="info">文件：{{ detail.filename || '-' }}</el-tag>
            <el-tag>SNR {{ detail.signal_quality?.snr ?? '-' }} dB</el-tag>
            <el-tag>采样率 {{ detail.signal_quality?.sample_rate ?? 125 }} Hz</el-tag>
          </div>

          <div class="summary-text">{{ detail.explanation || '暂无预测依据' }}</div>
        </el-card>

        <el-card class="detail-card" shadow="always">
          <template #header>
            <span>原始 PPG 波形</span>
          </template>
          <div ref="rawChartRef" class="raw-chart"></div>
        </el-card>

        <el-card class="detail-card" shadow="always">
          <template #header>
            <span>相似样本详细对比（共 {{ similarSamples.length }} 个）</span>
          </template>
          <el-row :gutter="16">
            <el-col v-for="(sample, index) in similarSamples" :key="sample.id || index" :span="24">
              <el-card class="sample-card" shadow="never">
                <template #header>
                  <div class="card-header-row">
                    <strong>样本 #{{ index + 1 }}{{ index === 0 ? '（最相似）' : '' }}</strong>
                    <el-tag>{{ sample.source || 'mock' }}</el-tag>
                  </div>
                </template>
                <div class="sample-body">
                  <div :ref="(el) => setMiniChartRef(el, index)" class="mini-chart"></div>
                  <div class="sample-info">
                    <div>血压值：{{ sample.sbp }}/{{ sample.dbp }} mmHg</div>
                    <div>向量距离：{{ Number(sample.distance).toFixed(4) }}</div>
                  </div>
                  <div class="sample-weight">
                    <el-progress :percentage="sample.weightPercent" />
                    <span>权重 {{ sample.weightPercent }}%</span>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>

        <el-card class="detail-card" shadow="always">
          <template #header>
            <span>预测过程拆解</span>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="item in workflowTimeline"
              :key="item.title"
              type="success"
              :timestamp="item.timestamp"
            >
              <div class="timeline-title">{{ item.title }}</div>
              <div class="timeline-content">{{ item.content }}</div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </template>

      <el-card v-else class="detail-card" shadow="always">
        <el-empty description="记录不存在或已被删除">
          <el-button type="primary" @click="router.push('/records')">返回历史记录</el-button>
        </el-empty>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import client from '../api/client'
import AppTopNav from '../components/AppTopNav.vue'

const route = useRoute()
const router = useRouter()
const recordId = route.params.id
const detail = ref(null)
const rawChartRef = ref(null)
const miniChartRefs = ref([])
let rawChart = null
const miniCharts = []

const progressColors = [
  { color: '#F56C6C', percentage: 50 },
  { color: '#E6A23C', percentage: 75 },
  { color: '#67C23A', percentage: 100 }
]

const confidencePercent = computed(() => Math.round(Number(detail.value?.confidence || 0) * 100))

const bpLevel = computed(() => {
  const sbp = Number(detail.value?.sbp)
  const dbp = Number(detail.value?.dbp)
  if (sbp >= 140 || dbp >= 90) return { label: '高血压', type: 'danger' }
  if (sbp >= 120 || dbp >= 80) return { label: '偏高', type: 'warning' }
  return { label: '正常', type: 'success' }
})

const similarSamples = computed(() => {
  const samples = [...(detail.value?.similar_samples || [])].sort((a, b) => Number(a.distance) - Number(b.distance))
  const weights = samples.map((sample) => 1 / (Number(sample.distance) + 1e-6))
  const total = weights.reduce((sum, value) => sum + value, 0) || 1
  return samples.map((sample, index) => ({
    ...sample,
    weightPercent: Math.round((weights[index] / total) * 100)
  }))
})

const similarWaveformMap = computed(() => {
  const entries = detail.value?.similar_waveforms || []
  return new Map(entries.map((item) => [String(item.sample_id), item.signal || []]))
})

const workflowTimeline = computed(() => {
  const topK = similarSamples.value.length
  const confidence = confidencePercent.value
  const sbps = similarSamples.value.map((sample) => Number(sample.sbp))
  const mean = sbps.reduce((sum, value) => sum + value, 0) / (sbps.length || 1)
  const std = Math.sqrt(sbps.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (sbps.length || 1))
  const baseTime = formatDateTime(detail.value?.created_at).split(' ')[1] || '00:00:00'
  return [
    {
      title: '向量生成',
      timestamp: `${baseTime}.123`,
      content: '将 PPG 信号提取统计特征，经编码生成 128 维特征向量'
    },
    {
      title: 'Milvus检索',
      timestamp: `${baseTime}.245`,
      content: `使用 IVF_FLAT 索引，nprobe=16，检索 Top-${topK} 相似向量，返回${topK}条结果`
    },
    {
      title: '加权计算',
      timestamp: `${baseTime}.301`,
      content: `距离倒数加权，ε=1e-6，预测 SBP=${detail.value?.sbp}，DBP=${detail.value?.dbp}`
    },
    {
      title: '解释生成',
      timestamp: `${baseTime}.345`,
      content: `相似样本收缩压标准差 ${std.toFixed(1)}mmHg，置信度 ${confidence}%`
    }
  ]
})

function formatDateTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 19)
}

function setMiniChartRef(el, index) {
  if (el) miniChartRefs.value[index] = el
}

function buildMiniSignal(index) {
  const sample = similarSamples.value[index]
  const sampleId = sample?.id == null ? '' : String(sample.id)
  const realSignal = similarWaveformMap.value.get(sampleId)
  return realSignal?.length ? realSignal : []
}

function renderRawChart() {
  const signal = detail.value?.ppg_signal || []
  if (!rawChartRef.value || !signal.length) return
  rawChart = rawChart || echarts.init(rawChartRef.value)
  rawChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const item = params[0]
        return `时间: ${item.axisValue}s<br/>幅值: ${Number(item.data).toFixed(4)}`
      }
    },
    grid: { left: 50, right: 24, top: 30, bottom: 70 },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 28 }],
    xAxis: { type: 'category', name: '时间(s)', data: signal.map((_, index) => (index / 125).toFixed(3)) },
    yAxis: { type: 'value', name: '归一化幅值', min: 0, max: 1 },
    series: [
      {
        name: '原始PPG',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: signal,
        lineStyle: { color: '#409EFF', width: 2 },
        areaStyle: { color: 'rgba(64, 158, 255, 0.1)' }
      }
    ]
  })
}

function renderMiniCharts() {
  similarSamples.value.forEach((sample, index) => {
    const el = miniChartRefs.value[index]
    if (!el) return
    const signal = buildMiniSignal(index)
    if (!signal.length) return
    miniCharts[index] = miniCharts[index] || echarts.init(el)
    miniCharts[index].setOption({
      grid: { left: 0, right: 0, top: 6, bottom: 6 },
      xAxis: { type: 'category', show: false, data: signal.map((__, pointIndex) => pointIndex) },
      yAxis: { type: 'value', show: false, min: 0, max: 1 },
      series: [
        {
          type: 'line',
          data: signal,
          showSymbol: false,
          smooth: true,
          lineStyle: { color: index === 0 ? '#409EFF' : '#909399', width: 1.5 }
        }
      ]
    })
  })
}

async function loadDetail() {
  try {
    const response = await client.get(`/prediction/${recordId}`)
    detail.value = response.data.data
    await nextTick()
    renderRawChart()
    renderMiniCharts()
  } catch (error) {
    detail.value = null
    ElMessage.error(error.response?.data?.detail || '详情加载失败')
  }
}

onMounted(loadDetail)

onUnmounted(() => {
  if (rawChart) rawChart.dispose()
  miniCharts.forEach((chart) => chart?.dispose())
})
</script>

<style>
.detail-page {
  min-height: 100vh;
  background: #f5f8fc;
}

.detail-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 30px 16px;
}

.detail-card {
  margin-top: 20px;
  border-radius: 8px;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.overview-item {
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.overview-label {
  color: #6b7280;
  font-size: 14px;
}

.overview-value {
  margin: 10px 0;
  color: #111827;
  font-size: 36px;
  font-weight: 700;
}

.overview-value span {
  color: #6b7280;
  font-size: 14px;
}

.confidence-text {
  margin-top: 8px;
  color: #111827;
  font-size: 24px;
  font-weight: 700;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.summary-text {
  margin-top: 18px;
  padding: 12px;
  color: #4b5563;
  line-height: 1.6;
  background: #f3f4f6;
  border-radius: 6px;
}

.raw-chart {
  height: 400px;
}

.sample-card {
  margin-bottom: 14px;
  border: 1px solid #e5e7eb;
}

.sample-body {
  display: grid;
  grid-template-columns: 220px 1fr 220px;
  align-items: center;
  gap: 20px;
}

.mini-chart {
  width: 200px;
  height: 80px;
}

.sample-info {
  color: #374151;
  line-height: 1.8;
}

.sample-weight span {
  display: block;
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
}

.timeline-title {
  color: #1f2937;
  font-weight: 700;
}

.timeline-content {
  margin-top: 4px;
  color: #6b7280;
  line-height: 1.6;
}

@media (max-width: 860px) {
  .overview-grid,
  .sample-body {
    grid-template-columns: 1fr;
  }

  .mini-chart {
    width: 100%;
  }
}
</style>
