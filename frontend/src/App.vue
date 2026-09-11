<template>
  <el-config-provider :locale="zhCn">
    <div class="shell">
    <aside>
      <div class="brand">
        <div class="logo">AQ</div>
        <div>
          <div class="name">AlphaQuant</div>
          <div class="tag">因子增强 · 风险平价</div>
        </div>
      </div>
      <nav>
        <router-link
          v-for="l in links"
          :key="l.to"
          :to="l.to"
          :data-testid="l.testId"
        >{{ l.label }}</router-link>
      </nav>
      <div class="src">
        <div class="src-label">数据源</div>
        <el-select :model-value="source" size="small" @change="onSource">
          <el-option label="离线演示（可断网）" value="offline" />
          <el-option label="自动（AKShare，失败降级）" value="auto" />
        </el-select>
        <p class="hint">公开或合成演示，不是实盘。</p>
      </div>
    </aside>
    <main>
      <header>
        <span>{{ $route.meta.title }}</span>
        <span class="badge-src">{{ source === 'offline' ? '离线演示' : '自动/可能降级' }}</span>
      </header>
<router-view />
    </main>
    </div>
  </el-config-provider>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { getSource, setSource } from './api/client'

const router = useRouter()
const source = ref(getSource())
const links = [
  { to: '/', label: '仪表盘', testId: 'nav-dashboard' },
  { to: '/screen', label: '选股', testId: 'nav-screen' },
  { to: '/backtest', label: '回测', testId: 'nav-backtest' },
  { to: '/portfolio', label: '组合', testId: 'nav-portfolio' },
  { to: '/risk', label: '风控', testId: 'nav-risk' },
  { to: '/suitability', label: '适当性', testId: 'nav-suitability' },
  { to: '/case2', label: '案例2', testId: 'nav-case2' },
]

function onSource(v) {
  setSource(v)
  source.value = v
  window.location.reload()
}

router.afterEach(() => {
  nextTick(() => ElMessage.closeAll())
})
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; }
aside { width: 220px; background: #0e1626; border-right: 1px solid var(--line); padding: 18px 14px; display: flex; flex-direction: column; }
.brand { display: flex; gap: 10px; align-items: center; margin-bottom: 22px; }
.logo { width: 36px; height: 36px; border-radius: 8px; background: var(--gold); color: #1a1406; font-weight: 800; display: grid; place-items: center; }
.name { font-weight: 700; }
.tag { color: var(--muted); font-size: 12px; }
nav { display: flex; flex-direction: column; gap: 6px; }
nav a { color: var(--muted); text-decoration: none; padding: 8px 10px; border-radius: 8px; }
nav a.router-link-active, nav a.router-link-exact-active { background: #1b263c; color: var(--text); }
.src { margin-top: auto; }
.src-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.hint { font-size: 11px; color: var(--muted); }
main { flex: 1; min-width: 0; }
header { height: 52px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; }
</style>
