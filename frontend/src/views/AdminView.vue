<template>
  <div class="admin-page">
    <AppTopNav active="admin" />

    <main class="admin-main">
      <template v-if="hasAdminPermission">
        <h1 class="admin-title">系统管理</h1>

        <el-card class="admin-card" shadow="always">
          <template #header>
            <div class="card-header">
              <span>系统配置</span>
            </div>
          </template>

          <el-form label-width="150px" class="config-form">
            <el-form-item v-for="item in configItems" :key="item.key" :label="item.label">
              <div class="config-row">
                <el-input-number
                  v-model="configs[item.key]"
                  :min="item.min"
                  :max="item.max"
                  :step="item.step"
                  controls-position="right"
                  class="config-input"
                />
                <el-button
                  size="small"
                  :type="savedKey === item.key ? 'success' : 'primary'"
                  :loading="savingKey === item.key"
                  @click="saveConfig(item.key)"
                >
                  {{ savedKey === item.key ? '已保存' : '保存' }}
                </el-button>
              </div>
            </el-form-item>
          </el-form>

          <el-button type="primary" plain @click="refreshCache">刷新全部缓存</el-button>
        </el-card>

        <el-card class="admin-card" shadow="always">
          <template #header>
            <div class="card-header">
              <span>特征库管理</span>
            </div>
          </template>

          <div class="feature-store-row">
            <div>
              <div class="feature-store-title">Milvus 特征数据</div>
              <div class="feature-store-desc">重建向量集合并导入预置和生成的模拟样本</div>
              <div v-if="featureStoreResult" class="feature-store-result">
                已导入 {{ featureStoreResult.inserted }} 条，集合 {{ featureStoreResult.collection }}
              </div>
            </div>
            <el-button type="primary" :loading="initializingMilvus" @click="initializeMilvus">
              初始化特征库
            </el-button>
          </div>
        </el-card>

        <el-card class="admin-card" shadow="always">
          <template #header>
            <div class="card-header">
              <span>系统健康状态</span>
              <el-button :icon="Refresh" circle :loading="healthLoading" @click="loadHealth" />
            </div>
          </template>

          <el-descriptions :column="1" border>
            <el-descriptions-item v-for="item in healthItems" :key="item.key" :label="item.label">
              <div class="health-row">
                <el-tag :type="isServiceHealthy(item.status) ? 'success' : 'danger'">
                  {{ isServiceHealthy(item.status) ? '正常' : '异常' }}
                </el-tag>
                <span>{{ item.message }}</span>
              </div>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card class="admin-card" shadow="always">
          <template #header>
            <div class="card-header">
              <span>用户管理</span>
            </div>
          </template>

          <el-table v-loading="usersLoading" :data="users" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" min-width="140" />
            <el-table-column prop="email" label="邮箱" min-width="220" />
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">
                  {{ row.role }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-switch
                  v-model="row.status"
                  :active-value="1"
                  :inactive-value="0"
                  :loading="savingUserId === row.id"
                  @change="updateUserStatus(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="注册时间" min-width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default>
                <el-button link disabled>查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-row">
            <el-pagination
              v-model:current-page="pagination.page"
              v-model:page-size="pagination.pageSize"
              background
              layout="total, prev, pager, next"
              :total="pagination.total"
              :page-size="pagination.pageSize"
              @current-change="loadUsers"
            />
          </div>
        </el-card>
      </template>

      <el-empty v-else description="无权访问此页面" class="admin-empty">
        <el-button type="primary" @click="router.push('/prediction')">返回首页</el-button>
      </el-empty>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import client from '../api/client'
import AppTopNav from '../components/AppTopNav.vue'
import { getStoredUser } from '../utils/auth'

const router = useRouter()
const currentUser = ref(getStoredUser())
const hasAdminPermission = computed(() => currentUser.value?.role === 'admin')

const configs = reactive({
  top_k_default: 5,
  confidence_threshold: 0.6,
  milvus_nprobe: 16,
  snr_threshold: 10
})
const configItems = [
  { key: 'top_k_default', label: 'Top-K 值', min: 3, max: 10, step: 1 },
  { key: 'confidence_threshold', label: '置信度阈值', min: 0, max: 1, step: 0.1 },
  { key: 'milvus_nprobe', label: 'Milvus nprobe', min: 1, max: 128, step: 1 },
  { key: 'snr_threshold', label: 'SNR 阈值', min: 5, max: 20, step: 1 }
]

const savingKey = ref('')
const savedKey = ref('')
const healthLoading = ref(false)
const initializingMilvus = ref(false)
const featureStoreResult = ref(null)
const health = reactive({
  mysql: { status: 'healthy', message: '连接正常' },
  milvus: { status: 'healthy', message: '连接正常' },
  redis: { status: 'healthy', message: '连接正常' },
  backend: { status: 'healthy', message: '服务正常' }
})
const healthItems = computed(() => [
  { key: 'mysql', label: 'MySQL', ...health.mysql },
  { key: 'milvus', label: 'Milvus', ...health.milvus },
  { key: 'redis', label: 'Redis', ...health.redis },
  { key: 'backend', label: '后端服务', ...health.backend }
])

const users = ref([])
const usersLoading = ref(false)
const savingUserId = ref(null)
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

function extractApiError(error, defaultMessage) {
  if (!error.response) return '网络连接失败，请检查服务是否启动'
  const detail = error.response.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) return detail.map((item) => item?.msg || JSON.stringify(item)).join('；')
  return defaultMessage
}

async function loadConfigs() {
  try {
    const response = await client.get('/admin/configs')
    const list = response.data.data || []
    list.forEach((item) => {
      if (Object.prototype.hasOwnProperty.call(configs, item.config_key)) {
        configs[item.config_key] = Number(item.config_value)
      }
    })
  } catch (error) {
    handlePermissionError(error, '配置加载失败')
  }
}

async function saveConfig(key) {
  savingKey.value = key
  try {
    await client.put(`/admin/configs/${key}`, {
      value: String(configs[key])
    })
    ElMessage.success('保存成功')
    savedKey.value = key
    window.setTimeout(() => {
      if (savedKey.value === key) savedKey.value = ''
    }, 1000)
  } catch (error) {
    ElMessage.error(`保存失败：${extractApiError(error, '值超出范围')}`)
  } finally {
    savingKey.value = ''
  }
}

async function refreshCache() {
  try {
    await client.post('/admin/configs/cache/refresh')
    ElMessage.success('配置缓存已刷新')
  } catch (error) {
    ElMessage.error(extractApiError(error, '配置缓存刷新失败'))
  }
}

async function initializeMilvus() {
  initializingMilvus.value = true
  try {
    const response = await client.post('/admin/milvus/initialize')
    featureStoreResult.value = response.data.data
    ElMessage.success(response.data.message || 'Milvus 特征库初始化完成')
  } catch (error) {
    ElMessage.error(extractApiError(error, 'Milvus 特征库初始化失败'))
  } finally {
    initializingMilvus.value = false
  }
}

async function loadHealth() {
  healthLoading.value = true
  try {
    const response = await client.get('/health')
    const services = response.data.data?.service_details || response.data.data?.services || {}
    ;['mysql', 'milvus', 'redis', 'backend'].forEach((key) => {
      if (services[key]) Object.assign(health[key], services[key])
    })
  } catch (error) {
    health.backend = { status: 'unhealthy', message: extractApiError(error, '健康状态加载失败') }
  } finally {
    healthLoading.value = false
  }
}

async function loadUsers() {
  usersLoading.value = true
  try {
    const response = await client.get('/admin/users', {
      params: {
        page: pagination.page,
        page_size: pagination.pageSize
      }
    })
    const data = response.data.data
    users.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    handlePermissionError(error, '用户列表加载失败')
  } finally {
    usersLoading.value = false
  }
}

async function updateUserStatus(row) {
  const nextStatus = row.status
  savingUserId.value = row.id
  try {
    await client.put(`/admin/users/${row.id}/status`, null, {
      params: { status: nextStatus }
    })
    ElMessage.success('用户状态已更新')
  } catch (error) {
    row.status = nextStatus === 1 ? 0 : 1
    ElMessage.error(extractApiError(error, '用户状态更新失败'))
  } finally {
    savingUserId.value = null
  }
}

function handlePermissionError(error, defaultMessage) {
  if (error.response?.status === 403) {
    currentUser.value = { ...currentUser.value, role: 'user' }
    return
  }
  ElMessage.error(extractApiError(error, defaultMessage))
}

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function isServiceHealthy(status) {
  return status === 'healthy' || status === 'connected'
}

onMounted(() => {
  if (!hasAdminPermission.value) return
  loadConfigs()
  loadHealth()
  loadUsers()
})
</script>

<style>
.admin-page {
  min-height: 100vh;
  background: #f5f8fc;
}

.admin-main {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 16px;
}

.admin-title {
  margin: 0 0 24px;
  color: #1f2937;
  font-size: 28px;
  font-weight: 700;
}

.admin-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #1f2937;
  font-size: 18px;
  font-weight: 700;
}

.config-form {
  max-width: 520px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.config-input {
  width: 200px;
}

.health-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feature-store-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.feature-store-title {
  color: #1f2937;
  font-size: 16px;
  font-weight: 700;
}

.feature-store-desc,
.feature-store-result {
  margin-top: 6px;
  color: #64748b;
  font-size: 14px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.admin-empty {
  margin-top: 120px;
}

@media (max-width: 720px) {
  .config-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
