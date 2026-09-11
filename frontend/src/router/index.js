import { createRouter, createWebHistory } from 'vue-router'

// 路由级懒加载：每个页面独立 chunk，首屏只加载当前页，
// ECharts/Table 等重依赖随使用页面按需到达。
const routes = [
  { path: '/', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '仪表盘' } },
  { path: '/screen', name: 'screen', component: () => import('../views/Screen.vue'), meta: { title: '选股' } },
  { path: '/backtest', name: 'backtest', component: () => import('../views/Backtest.vue'), meta: { title: '回测' } },
  { path: '/portfolio', name: 'portfolio', component: () => import('../views/Portfolio.vue'), meta: { title: '组合' } },
  { path: '/risk', name: 'risk', component: () => import('../views/Risk.vue'), meta: { title: '风控' } },
  { path: '/suitability', name: 'suitability', component: () => import('../views/Suitability.vue'), meta: { title: '适当性' } },
  { path: '/case2', name: 'case2', component: () => import('../views/Case2.vue'), meta: { title: '案例2' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
