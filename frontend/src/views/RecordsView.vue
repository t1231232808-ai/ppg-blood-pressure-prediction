<template>
  <div class="records-page">
    <AppTopNav active="records" />

    <main class="records-main">
      <h1 class="records-title">历史记录</h1>

      <el-card class="records-card" shadow="always">
        <el-form inline :model="filters" class="filter-form">
          <el-form-item label="日期范围">
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
          <el-form-item label="血压级别">
            <el-select v-model="filters.bpLevel" multiple placeholder="血压级别" style="width: 240px">
              <el-option label="正常" value="normal" />
              <el-option label="偏高" value="elevated" />
              <el-option label="高血压" value="hypertension" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="queryRecords">查询</el-button>
            <el-button plain @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-row :gutter="20" class="stats-row">
        <el-col :xs="24" :md="14">
          <el-card class="records-card" shadow="always">
            <template #header>
              <span>近7天血压趋势</span>
            </template>
            <div class="stats-summary">近7天平均: SBP {{ stats.avg_sbp }} / DBP {{ stats.avg_dbp }}</div>
            <div ref="trendChartRef" class="stats-chart"></div>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="10">
          <el-card class="records-card" shadow="always">
            <template #header>
              <span>血压级别分布</span>
            </template>
            <div ref="pieChartRef" class="stats-chart"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="records-card" shadow="always">
        <template #header>
          <span>预测记录列表</span>
        </template>
        <el-table :data="records" stripe border class="records-table">
          <el-table-column prop="id" label="编号" width="80" />
          <el-table-column label="预测时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="收缩压" width="120">
            <template #default="{ row }">
              <span>{{ row.sbp_predicted }}</span>
              <el-tag class="bp-tag" :type="getBpLevel(row).type">{{ getBpLevel(row).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="舒张压" width="120">
            <template #default="{ row }">
              <span>{{ row.dbp_predicted }}</span>
              <el-tag class="bp-tag" :type="getBpLevel(row).type">{{ getBpLevel(row).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="级别" width="120">
            <template #default="{ row }">
              <el-tag :type="getBpLevel(row).type">{{ getBpLevel(row).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ Math.round(Number(row.confidence) * 100) }}%</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="router.push(`/prediction/${row.id}`)">查看</el-button>
              <el-button type="danger" link @click="deleteRecord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!records.length && !loading" description="暂无历史记录" />
        <div class="pagination-row">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            background
            layout="total, sizes, prev, pager, next"
            :page-sizes="[10, 20, 50]"
            :total="pagination.total"
            @size-change="loadRecords"
            @current-change="loadRecords"
          />
        </div>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import client from '../api/client'
import AppTopNav from '../components/AppTopNav.vue'

const router = useRouter()
const loading = ref(false)
const records = ref([])
const trendChartRef = ref(null)
const pieChartRef = ref(null)
let trendChart = null
let pieChart = null

const filters = reactive({
  dateRange: [],
  bpLevel: []
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const stats = reactive({
  avg_sbp: 0,
  avg_dbp: 0,
  recent_7days: [],
  level_distribution: { normal: 0, elevated: 0, hypertension: 0 }
})

function formatDateTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 19)
}

function getBpLevel(row) {
  const sbp = Number(row.sbp_predicted)
  const dbp = Number(row.dbp_predicted)
  if (sbp >= 140 || dbp >= 90) return { value: 'hypertension', label: '高血压', type: 'danger' }
  if (sbp >= 120 || dbp >= 80) return { value: 'elevated', label: '偏高', type: 'warning' }
  return { value: 'normal', label: '正常', type: 'success' }
}

function buildQueryParams() {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }
  if (filters.dateRange?.length === 2) {
    params.start_date = filters.dateRange[0]
    params.end_date = filters.dateRange[1]
  }
  if (filters.bpLevel?.length) {
    params.bp_level = filters.bpLevel
  }
  return params
}

async function loadRecords() {
  loading.value = true
  try {
    const response = await client.get('/records', { params: buildQueryParams() })
    records.value = response.data.data.items
    pagination.total = response.data.data.total
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '历史记录加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  const response = await client.get('/records/stats')
  Object.assign(stats, response.data.data)
  await nextTick()
  renderCharts()
}

function queryRecords() {
  pagination.page = 1
  loadRecords()
  loadStats()
}

function resetFilters() {
  filters.dateRange = []
  filters.bpLevel = []
  pagination.page = 1
  loadRecords()
  loadStats()
}

async function deleteRecord(row) {
  try {
    await ElMessageBox.confirm('删除后无法恢复，是否继续？', '确认删除', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await client.delete(`/records/${row.id}`)
    ElMessage.success('删除成功')
    loadRecords()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

function renderCharts() {
  renderTrendChart()
  renderPieChart()
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  trendChart = trendChart || echarts.init(trendChartRef.value)
  const days = stats.recent_7days || []
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['收缩压', '舒张压'] },
    grid: { left: 40, right: 20, top: 35, bottom: 30 },
    xAxis: { type: 'category', data: days.map((item) => item.date.slice(5)) },
    yAxis: { type: 'value', name: 'mmHg' },
    series: [
      { name: '收缩压', type: 'line', smooth: true, data: days.map((item) => item.avg_sbp), lineStyle: { color: '#F56C6C' } },
      { name: '舒张压', type: 'line', smooth: true, data: days.map((item) => item.avg_dbp), lineStyle: { color: '#409EFF' } }
    ]
  })
}

function renderPieChart() {
  if (!pieChartRef.value) return
  pieChart = pieChart || echarts.init(pieChartRef.value)
  const distribution = stats.level_distribution || {}
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    color: ['#67C23A', '#E6A23C', '#F56C6C'],
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        data: [
          { name: '正常', value: distribution.normal || 0 },
          { name: '偏高', value: distribution.elevated || 0 },
          { name: '高血压', value: distribution.hypertension || 0 }
        ]
      }
    ]
  })
}

onMounted(() => {
  loadRecords()
  loadStats()
})

onUnmounted(() => {
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style>
.records-page {
  min-height: 100vh;
  background: #f5f8fc;
}

.records-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 30px 16px;
}

.records-title {
  margin: 0 0 20px;
  color: #1f2937;
  font-size: 26px;
  font-weight: 700;
}

.records-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.filter-form {
  align-items: center;
}

.stats-row {
  margin-bottom: 0;
}

.stats-summary {
  margin-bottom: 8px;
  color: #4b5563;
  font-size: 14px;
}

.stats-chart {
  height: 200px;
}

.records-table .el-table__row {
  height: 48px;
}

.bp-tag {
  margin-left: 8px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
</style>
