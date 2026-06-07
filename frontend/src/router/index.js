import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import LoginView from '../views/LoginView.vue'
import PredictionView from '../views/PredictionView.vue'
import PredictionDetailView from '../views/PredictionDetailView.vue'
import ResultView from '../views/ResultView.vue'
import RecordsView from '../views/RecordsView.vue'
import AdminView from '../views/AdminView.vue'
import { getToken, isAdmin } from '../utils/auth'

const routes = [
  {
    path: '/',
    redirect: () => (getToken() ? '/prediction' : '/login')
  },
  { path: '/dashboard', redirect: '/prediction' },
  { path: '/login', component: LoginView },
  { path: '/prediction', component: PredictionView, meta: { requiresAuth: true } },
  { path: '/result', component: ResultView, meta: { requiresAuth: true } },
  { path: '/prediction/:id', component: PredictionDetailView, meta: { requiresAuth: true } },
  { path: '/records', component: RecordsView, meta: { requiresAuth: true } },
  { path: '/admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !getToken()) {
    ElMessage.warning('请先登录')
    return '/login'
  }
  if (to.meta.requiresAdmin && !isAdmin()) {
    ElMessage.warning('需要管理员权限')
    return '/prediction'
  }
  return true
})

export default router
