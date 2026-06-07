<template>
  <header class="app-top-nav">
    <div class="app-top-logo" @click="router.push('/prediction')">PPG血压预测</div>
    <div class="app-top-actions">
      <el-button :type="active === 'prediction' ? 'primary' : ''" link @click="router.push('/prediction')">
        PPG信号上传
      </el-button>
      <el-button :type="active === 'result' ? 'primary' : ''" link @click="router.push('/result')">
        实时预测
      </el-button>
      <el-button :type="active === 'records' ? 'primary' : ''" link @click="router.push('/records')">
        历史记录
      </el-button>
      <el-button
        v-if="isAdminUser"
        class="admin-nav-button"
        :class="{ active: active === 'admin' }"
        @click="router.push('/admin')"
      >
        系统管理
      </el-button>
      <el-dropdown @command="handleUserCommand">
        <span class="app-user-dropdown">
          {{ currentUser?.username || '用户' }}
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { clearAuth, getStoredUser } from '../utils/auth'

defineProps({
  active: {
    type: String,
    default: ''
  }
})

const router = useRouter()
const currentUser = ref(getStoredUser())
const isAdminUser = computed(() => currentUser.value?.role === 'admin')

function handleUserCommand(command) {
  if (command === 'logout') {
    clearAuth()
    router.push('/login')
  }
}
</script>

<style>
.app-top-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.app-top-logo {
  color: #0b1f33;
  font-size: 30px;
  font-weight: 800;
  cursor: pointer;
}

.app-top-actions {
  display: flex;
  align-items: center;
  gap: 28px;
}

.app-top-actions .el-button {
  height: 40px;
  padding: 0;
  color: #4b5563;
  font-size: 18px;
}

.app-top-actions .el-button.el-button--primary {
  color: #409eff;
}

.app-top-actions .admin-nav-button {
  height: 36px;
  padding: 0 16px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  font-size: 18px;
}

.app-top-actions .admin-nav-button:hover,
.app-top-actions .admin-nav-button.active {
  color: #ffffff;
  background: #409eff;
  border-color: #409eff;
}

.app-user-dropdown {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px;
  color: #111827;
  font-size: 20px;
  line-height: 36px;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  outline: none;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.app-user-dropdown:hover,
.app-user-dropdown:focus-visible {
  background: #f8fafc;
  border-color: #d1d5db;
}

.app-user-dropdown .el-icon {
  flex: 0 0 auto;
  font-size: 16px;
}

@media (max-width: 860px) {
  .app-top-nav {
    height: auto;
    min-height: 72px;
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
    padding: 14px 18px;
  }

  .app-top-logo {
    font-size: 24px;
  }

  .app-top-actions {
    flex-wrap: wrap;
    gap: 14px;
  }

  .app-top-actions .el-button,
  .app-user-dropdown {
    font-size: 16px;
  }
}
</style>
