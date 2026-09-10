import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Screen from '../views/Screen.vue'
import Backtest from '../views/Backtest.vue'
import Portfolio from '../views/Portfolio.vue'
import Risk from '../views/Risk.vue'
import Suitability from '../views/Suitability.vue'
import Case2 from '../views/Case2.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '仪表盘' } },
    { path: '/screen', name: 'screen', component: Screen, meta: { title: '选股' } },
    { path: '/backtest', name: 'backtest', component: Backtest, meta: { title: '回测' } },
    { path: '/portfolio', name: 'portfolio', component: Portfolio, meta: { title: '组合' } },
    { path: '/risk', name: 'risk', component: Risk, meta: { title: '风控' } },
    { path: '/suitability', name: 'suitability', component: Suitability, meta: { title: '适当性' } },
    { path: '/case2', name: 'case2', component: Case2, meta: { title: '案例2' } },
  ],
})

export default router
