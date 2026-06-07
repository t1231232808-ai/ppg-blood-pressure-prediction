<template>
  <div class="upload-page">
    <AppTopNav active="prediction" />

    <main class="upload-main">
      <section class="upload-panel">
        <div class="upload-title-block">
          <h1>PPG 信号上传</h1>
          <p>上传脉搏波数据或选择模拟样本开始预测</p>
        </div>

        <div class="mode-grid">
          <el-card
            class="mode-card"
            :class="{ active: mode === 'file' }"
            shadow="never"
            @click="selectMode('file')"
          >
            <el-icon class="mode-icon"><FolderOpened /></el-icon>
            <h2>上传 CSV 文件</h2>
            <p>支持 .csv 格式，最大 5MB</p>
          </el-card>

          <el-card
            class="mode-card"
            :class="{ active: mode === 'mock' }"
            shadow="never"
            @click="selectMode('mock')"
          >
            <el-icon class="mode-icon"><DataAnalysis /></el-icon>
            <h2>使用模拟数据</h2>
            <p>系统预置 20 组模拟数据，快速体验</p>
          </el-card>
        </div>

        <div v-if="mode === 'file'" class="mode-content">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :show-file-list="false"
            accept=".csv"
            :before-upload="beforeUpload"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            class="ppg-uploader"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">点击或拖拽文件到此处上传</div>
            <template #tip>
              <div class="upload-tip">支持 .csv 格式，≤5MB</div>
            </template>
          </el-upload>

          <div v-if="selectedFile" class="file-info">
            <span>{{ selectedFile.name }}</span>
            <span>{{ formatFileSize(selectedFile.size) }}</span>
            <el-button link type="danger" @click="clearSelectedFile">移除</el-button>
          </div>

          <el-alert
            class="requirements-alert"
            type="info"
            :closable="false"
            title="文件要求：包含 timestamp 和 ppg_value 两列；采样率 125Hz，时长 8~12 秒；数据行数 1000~1500"
          />
        </div>

        <div v-else class="mode-content">
          <el-select v-model="selectedMockId" class="mock-select" placeholder="请选择模拟数据">
            <el-option
              v-for="item in mockOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <el-button
          type="primary"
          size="large"
          class="next-button"
          :loading="loading"
          :disabled="!canStart"
          @click="startPrediction"
        >
          下一步：开始预测
        </el-button>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, FolderOpened, UploadFilled } from '@element-plus/icons-vue'
import client from '../api/client'
import AppTopNav from '../components/AppTopNav.vue'
import { usePredictionState } from '../utils/predictionState'

const router = useRouter()
const { setLatestResult } = usePredictionState()
const mode = ref('file')
const selectedFile = ref(null)
const selectedMockId = ref('')
const loading = ref(false)
const uploadRef = ref(null)
const mockOptions = ref([])

async function loadMockOptions() {
  try {
    const response = await client.get('/prediction/mock/options')
    mockOptions.value = (response.data.data.items || []).map((item) => ({
      value: item.mock_id,
      label: `${item.mock_id} - ${item.name} (SBP~${item.sbp})`
    }))
  } catch (error) {
    ElMessage.error(extractApiError(error))
  }
}

const canStart = computed(() => {
  if (mode.value === 'file') return Boolean(selectedFile.value)
  return Boolean(selectedMockId.value)
})

function selectMode(nextMode) {
  mode.value = nextMode
}

function beforeUpload(file) {
  const isCSV = file.name.toLowerCase().endsWith('.csv')
  const isLt5M = file.size / 1024 / 1024 <= 5
  if (!isCSV) {
    ElMessage.error('仅支持 CSV 格式文件')
    return false
  }
  if (!isLt5M) {
    ElMessage.error('文件大小不能超过 5MB')
    return false
  }
  return true
}

function handleFileChange(uploadFile) {
  if (!beforeUpload(uploadFile.raw)) return
  selectedFile.value = uploadFile.raw
}

function handleFileRemove() {
  selectedFile.value = null
}

function clearSelectedFile() {
  selectedFile.value = null
  uploadRef.value?.clearFiles()
}

function formatFileSize(size) {
  return `${(size / 1024).toFixed(1)} KB`
}

function extractApiError(error) {
  if (!error.response) return '网络连接失败'
  const detail = error.response.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) return detail.map((item) => item?.msg || JSON.stringify(item)).join('；')
  return error.response.data?.message || '请求失败'
}

async function startPrediction() {
  loading.value = true
  try {
    let response
    if (mode.value === 'file') {
      const formData = new FormData()
      formData.append('file', selectedFile.value)
      response = await client.post('/prediction/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    } else {
      response = await client.post('/prediction/mock', { mock_id: selectedMockId.value })
    }
    setLatestResult(response.data.data)
    router.push('/result')
  } catch (error) {
    ElMessage.error(extractApiError(error))
  } finally {
    loading.value = false
  }
}

onMounted(loadMockOptions)

</script>

<style>
.upload-page {
  min-height: 100vh;
  background: #f5f8fc;
}

.upload-main {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 16px;
}

.upload-panel {
  padding: 32px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.upload-title-block {
  margin-bottom: 24px;
  text-align: center;
}

.upload-title-block h1 {
  margin: 0;
  color: #1f2937;
  font-size: 26px;
  font-weight: 700;
}

.upload-title-block p {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 14px;
}

.mode-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.mode-card {
  min-height: 150px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.mode-card:hover,
.mode-card.active {
  border-color: #409eff;
  box-shadow: 0 6px 18px rgba(64, 158, 255, 0.16);
}

.mode-card.active {
  transform: translateY(-2px);
}

.mode-card .el-card__body {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.mode-icon {
  color: #409eff;
  font-size: 38px;
}

.mode-card h2 {
  margin: 14px 0 8px;
  font-size: 18px;
  color: #1f2937;
}

.mode-card p {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.mode-content {
  margin-top: 24px;
  margin-bottom: 24px;
}

.ppg-uploader .el-upload-dragger {
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-style: dashed;
}

.upload-icon {
  color: #409eff;
  font-size: 42px;
}

.upload-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 13px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  color: #4b5563;
  font-size: 14px;
}

.requirements-alert {
  margin-top: 16px;
}

.mock-select {
  width: 100%;
}

.next-button {
  width: 100%;
  height: 44px;
  border-radius: 4px;
}

@media (max-width: 720px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }

  .upload-panel {
    padding: 24px;
  }
}
</style>
