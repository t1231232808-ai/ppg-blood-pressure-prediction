<template>
  <div class="login-page">
    <div class="login-header">
      <h1>PPG 血压智能预测系统</h1>
      <p>基于脉搏波信号的血压智能预测</p>
    </div>

    <div class="login-card">
      <el-tabs v-model="activeTab" class="auth-tabs" stretch>
        <el-tab-pane label="登录" name="login">
          <Transition name="tab-fade" mode="out-in">
            <el-form
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              class="auth-form"
              @keyup.enter="handleLogin"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="loginForm.username"
                  :prefix-icon="User"
                  placeholder="请输入用户名或邮箱"
                  autocomplete="username"
                />
              </el-form-item>

              <el-form-item prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  :prefix-icon="Lock"
                  placeholder="请输入密码"
                  autocomplete="current-password"
                  show-password
                />
              </el-form-item>

              <el-button type="primary" size="large" class="submit-button" :loading="loading" @click="handleLogin">
                确认登录
              </el-button>

              <div class="switch-line">
                还没有账号？<button type="button" @click="switchToRegister">立即注册</button>
              </div>
            </el-form>
          </Transition>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <Transition name="tab-fade" mode="out-in">
            <el-form
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              class="auth-form"
              @keyup.enter="handleRegister"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="registerForm.username"
                  :prefix-icon="User"
                  placeholder="请输入用户名，3-50字符"
                  autocomplete="username"
                />
              </el-form-item>

              <el-form-item prop="email">
                <el-input
                  v-model="registerForm.email"
                  :prefix-icon="Message"
                  placeholder="请输入邮箱地址"
                  autocomplete="email"
                />
              </el-form-item>

              <el-form-item prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  :prefix-icon="Lock"
                  placeholder="请输入密码，6-20字符"
                  autocomplete="new-password"
                  show-password
                />
              </el-form-item>

              <el-form-item prop="confirmPassword">
                <el-input
                  v-model="registerForm.confirmPassword"
                  type="password"
                  :prefix-icon="Lock"
                  placeholder="请再次输入密码"
                  autocomplete="new-password"
                  show-password
                />
              </el-form-item>

              <el-button type="primary" size="large" class="submit-button" :loading="loading" @click="handleRegister">
                确认注册
              </el-button>

              <div class="switch-line">
                已有账号？<button type="button" @click="switchToLogin">立即登录</button>
              </div>
            </el-form>
          </Transition>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Message, User } from '@element-plus/icons-vue'
import { setAuth } from '../utils/auth'

const API_BASE_URL = 'http://localhost:8000/api/v1'
const router = useRouter()
const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref()
const registerFormRef = ref()

const emailPattern = /^[\w-]+(\.[\w-]+)*@[\w-]+(\.[\w-]+)+$/

const loginForm = reactive({
  username: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

function validateConfirmPassword(_rule, value, callback) {
  if (!value) {
    callback(new Error('请再次输入密码'))
    return
  }
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const loginRules = {
  username: [
    { required: true, message: '请输入用户名或邮箱', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名/邮箱长度应为 3-50 字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为 6-20 字符', trigger: 'blur' }
  ]
}

const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度应为 3-50 字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { pattern: emailPattern, message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度应为 6-20 字符', trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
}

function extractErrorMessage(error) {
  if (!error.response) return '网络连接失败，请检查服务是否启动'
  const detail = error.response.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => item?.msg || item?.message || JSON.stringify(item)).join('；')
  }
  return error.response.data?.message || '请求失败'
}

function switchToRegister() {
  activeTab.value = 'register'
}

function switchToLogin() {
  activeTab.value = 'login'
}

async function handleLogin() {
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const response = await axios.post(
      `${API_BASE_URL}/auth/login`,
      {
        username: loginForm.username,
        password: loginForm.password
      },
      {
        headers: { 'Content-Type': 'application/json' }
      }
    )
    setAuth(response.data.data.access_token, response.data.data.user)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (error) {
    ElMessage.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await axios.post(
      `${API_BASE_URL}/auth/register`,
      {
        username: registerForm.username,
        email: registerForm.email,
        password: registerForm.password
      },
      {
        headers: { 'Content-Type': 'application/json' }
      }
    )
    ElMessage.success('注册成功，请登录')
    loginForm.username = registerForm.username
    loginForm.password = ''
    activeTab.value = 'login'
  } catch (error) {
    ElMessage.error(extractErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<style>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
}

.login-header {
  margin-bottom: 24px;
  text-align: center;
  color: #0d47a1;
}

.login-header h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0;
}

.login-header p {
  margin: 10px 0 0;
  font-size: 15px;
  color: #1565c0;
}

.login-card {
  width: 420px;
  max-width: 100%;
  padding: 28px 32px 30px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 12px 30px rgba(13, 71, 161, 0.18);
}

.auth-tabs .el-tabs__header {
  margin-bottom: 24px;
}

.auth-tabs .el-tabs__item {
  font-size: 16px;
  color: #607d8b;
}

.auth-tabs .el-tabs__item.is-active {
  color: #1565c0;
  font-weight: 600;
}

.auth-form {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.auth-form .el-form-item {
  margin-bottom: 22px;
}

.auth-form .el-input__wrapper {
  min-height: 44px;
  border-radius: 4px;
}

.auth-form .el-input__inner {
  height: 44px;
  font-size: 14px;
}

.submit-button {
  width: 100%;
  height: 44px;
  border-radius: 4px;
  font-size: 15px;
}

.switch-line {
  margin-top: 18px;
  text-align: center;
  color: #607d8b;
  font-size: 14px;
}

.switch-line button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #1565c0;
  font-size: 14px;
  cursor: pointer;
}

.switch-line button:hover {
  color: #0d47a1;
  text-decoration: underline;
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
