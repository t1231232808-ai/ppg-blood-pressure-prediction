import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import LoginView from './LoginView.vue'
import PredictionView from './PredictionView.vue'
import RecordsView from './RecordsView.vue'

const mocks = vi.hoisted(() => ({
  routerPush: vi.fn(),
  setLatestResult: vi.fn(),
  axiosPost: vi.fn(),
  clientGet: vi.fn(),
  clientPost: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.routerPush })
}))

vi.mock('axios', () => ({
  default: {
    post: (...args) => mocks.axiosPost(...args)
  }
}))

vi.mock('../api/client', () => ({
  default: {
    get: (...args) => mocks.clientGet(...args),
    post: (...args) => mocks.clientPost(...args)
  }
}))

vi.mock('../utils/auth', () => ({
  setAuth: vi.fn(),
  getToken: vi.fn(() => 'token'),
  clearAuth: vi.fn(),
  isAdmin: vi.fn(() => false)
}))

vi.mock('../utils/predictionState', () => ({
  usePredictionState: () => ({
    setLatestResult: mocks.setLatestResult,
    getLatestResult: vi.fn()
  })
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: mocks.messageSuccess,
      error: mocks.messageError,
      warning: vi.fn()
    },
    ElMessageBox: {
      confirm: vi.fn()
    }
  }
})

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    dispose: vi.fn()
  }))
}))

const AppTopNavStub = {
  template: '<nav data-test="top-nav"></nav>'
}

function mountWithStubs(component) {
  return mount(component, {
    global: {
      stubs: {
        AppTopNav: AppTopNavStub,
        Transition: false,
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<section><slot /></section>' },
        'el-form': {
          expose: ['validate'],
          methods: {
            validate() {
              return Promise.resolve(true)
            }
          },
          template: '<form><slot /></form>'
        },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': {
          props: ['modelValue', 'placeholder'],
          emits: ['update:modelValue'],
          template: '<input :placeholder="placeholder" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
        },
        'el-button': {
          template: '<button :disabled="$attrs.disabled" @click="$emit(\'click\', $event)"><slot /></button>'
        },
        'el-card': { template: '<section v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></section>' },
        'el-icon': { template: '<i><slot /></i>' },
        'el-upload': { template: '<div><slot /><slot name="tip" /></div>' },
        'el-alert': { props: ['title'], template: '<div>{{ title }}</div>' },
        'el-select': {
          props: ['modelValue', 'placeholder'],
          emits: ['update:modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option value="">{{ placeholder }}</option><slot /></select>'
        },
        'el-option': {
          props: ['label', 'value'],
          template: '<option :value="value">{{ label }}</option>'
        },
        'el-row': { template: '<div><slot /></div>' },
        'el-col': { template: '<div><slot /></div>' },
        'el-date-picker': { template: '<input />' },
        'el-table': {
          props: ['data'],
          template: '<table><tbody><tr v-for="row in data" :key="row.id"><td>{{ row.id }}</td><td>{{ row.sbp_predicted }}</td><td>{{ row.dbp_predicted }}</td></tr></tbody></table>'
        },
        'el-table-column': { template: '<td><slot /></td>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-empty': { props: ['description'], template: '<div>{{ description }}<slot /></div>' },
        'el-pagination': { template: '<div></div>' }
      }
    }
  })
}

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset())
})

describe('login page validation flow', () => {
  it('submits login and navigates to dashboard', async () => {
    mocks.axiosPost.mockResolvedValue({
      data: {
        data: {
          access_token: 'jwt-token',
          user: { id: 1, username: 'admin', role: 'admin' }
        }
      }
    })
    const wrapper = mountWithStubs(LoginView)

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('password123')
    await wrapper.find('button.submit-button').trigger('click')
    await flushPromises()

    expect(mocks.axiosPost).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/auth/login',
      { username: 'admin', password: 'password123' },
      { headers: { 'Content-Type': 'application/json' } }
    )
    expect(mocks.messageSuccess).toHaveBeenCalledWith('登录成功')
    expect(mocks.routerPush).toHaveBeenCalledWith('/dashboard')
  })
})

describe('prediction page flow', () => {
  it('loads mock options and starts mock prediction', async () => {
    mocks.clientGet.mockResolvedValue({
      data: {
        data: {
          items: [
            { mock_id: 'mock_001', name: '正常血压样本A', sbp: 120 },
            { mock_id: 'mock_002', name: '正常血压样本B', sbp: 115 }
          ]
        }
      }
    })
    mocks.clientPost.mockResolvedValue({ data: { data: { record_id: 12, sbp: 120, dbp: 78 } } })

    const wrapper = mountWithStubs(PredictionView)
    await flushPromises()

    expect(mocks.clientGet).toHaveBeenCalledWith('/prediction/mock/options')
    const mockModeCard = wrapper.findAll('.mode-card').find((item) => item.text().includes('使用模拟数据'))
    await mockModeCard.trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('mock_002 - 正常血压样本B (SBP~115)')

    await wrapper.find('select').setValue('mock_002')
    await wrapper.find('.next-button').trigger('click')
    await flushPromises()

    expect(mocks.clientPost).toHaveBeenCalledWith('/prediction/mock', { mock_id: 'mock_002' })
    expect(mocks.setLatestResult).toHaveBeenCalledWith({ record_id: 12, sbp: 120, dbp: 78 })
    expect(mocks.routerPush).toHaveBeenCalledWith('/result')
  })
})

describe('records page', () => {
  it('renders history records from API', async () => {
    mocks.clientGet.mockImplementation((url) => {
      if (url === '/records') {
        return Promise.resolve({
          data: {
            data: {
              items: [{ id: 7, sbp_predicted: 122, dbp_predicted: 80, confidence: 0.8, created_at: '2026-05-10T10:00:00' }],
              total: 1
            }
          }
        })
      }
      if (url === '/records/stats') {
        return Promise.resolve({
          data: {
            data: {
              avg_sbp: 122,
              avg_dbp: 80,
              recent_7days: [],
              level_distribution: { normal: 0, elevated: 1, hypertension: 0 }
            }
          }
        })
      }
      return Promise.reject(new Error(`unexpected url ${url}`))
    })

    const wrapper = mountWithStubs(RecordsView)
    await flushPromises()

    expect(mocks.clientGet).toHaveBeenCalledWith('/records', { params: { page: 1, page_size: 10 } })
    expect(mocks.clientGet).toHaveBeenCalledWith('/records/stats')
    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).toContain('122')
    expect(wrapper.text()).toContain('80')
  })
})
