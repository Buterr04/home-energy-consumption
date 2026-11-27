import { createRouter, createWebHashHistory } from 'vue-router'
import AdminView from './views/AdminView.vue'
import OverviewView from './views/OverviewView.vue'
import AnalysisView from './views/AnalysisView.vue'
import PredictView from './views/PredictView.vue'
import ReportsView from './views/ReportsView.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    {
      path: '/overview',
      name: 'overview',
      component: OverviewView,
      meta: { label: '能源总览', icon: 'layout' }
    },
    {
      path: '/analysis',
      name: 'analysis',
      component: AnalysisView,
      meta: { label: '用电分析', icon: 'chart' }
    },
    {
      path: '/predict',
      name: 'predict',
      component: PredictView,
      meta: { label: '智能预测', icon: 'sparkles' }
    },
    {
      path: '/reports',
      name: 'reports',
      component: ReportsView,
      meta: { label: '报告中心', icon: 'file' }
    },
    {
      path: '/admin',
      name: 'admin',
      component: AdminView,
      meta: { label: '管理控制台', icon: 'shield', admin: true }
    },
    { path: '/:pathMatch(.*)*', redirect: '/overview' }
  ]
})
