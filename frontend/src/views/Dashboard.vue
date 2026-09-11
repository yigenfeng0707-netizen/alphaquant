<template>
  <div class="page">
    <el-alert :title="banner" type="warning" :closable="false" show-icon />
    <h2>案例 1 · 10 万元稳健配置</h2>
    <p class="sub">因子选股 → 风险平价 → VaR / 压力测试。夏普对比为样本内历史模拟，不是收益承诺。</p>
    <el-button type="primary" data-testid="btn-case1" :loading="loading" @click="runCase">一键演示案例 1</el-button>
    <el-button data-testid="btn-go-screen" @click="go('/screen')">去选股</el-button>
    <el-button data-testid="btn-go-suitability" @click="go('/suitability')">适当性问卷</el-button>
    <el-button data-testid="btn-go-case2" @click="go('/case2')">打开案例 2</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">
      <span>{{ error }}</span>
      <el-button type="warning" size="small" style="margin-left:12px" :loading="loading" @click="runCase">重试</el-button>
    </div>
    <template v-else-if="!loading">
      <div class="placeholder-box" style="margin-top:12px">
        点击上方「一键演示案例 1」开始 — 因子选股 → 风险平价 → VaR 全链路。
      </div>
    </template>
    <template v-if="data">
      <div class="kpi-row" style="margin-top:16px">
        <div class="kpi">
          <div class="label">数据源</div>
          <div class="value" style="font-size:16px">{{ sourceLabel }}</div>
        </div>
        <div class="kpi">
          <div class="label">风险平价夏普</div>
          <div class="value up">{{ num(data.sharpe_rp) }}</div>
        </div>
        <div class="kpi">
          <div class="label">等权夏普</div>
          <div class="value">{{ num(data.sharpe_eq) }}</div>
        </div>
        <div class="kpi">
          <div class="label">平价是否优于等权</div>
          <div class="value" :class="data.sharpe_rp_better ? 'up' : 'down'">{{ data.sharpe_rp_better ? '是' : '否' }}</div>
        </div>
      </div>
      <el-row :gutter="16">
        <el-col :span="14">
          <el-card>
            <template #header>净值对照（风险平价 vs 等权）</template>
            <div ref="chartEl" data-testid="chart-case1" class="chart"></div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card>
            <template #header>入选标的（演示）</template>
            <el-table :data="data.picks" size="small" height="320">
              <el-table-column prop="code" label="代码" width="88" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="composite" label="综合分" width="90">
                <template #default="{ row }">{{ num(row.composite) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
      <el-row :gutter="16" style="margin-top:16px">
        <el-col :span="8">
          <el-card>
            <template #header>10 万名义本金（样本内）</template>
            <p>风险平价期末：{{ money(data.notional?.rp_end_value) }}</p>
            <p>等权期末：{{ money(data.notional?.eq_end_value) }}</p>
            <p class="sub">含近似交易成本，非实盘成交。</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card>
            <template #header>日度 95% VaR</template>
            <p class="kpi value down" style="font-size:22px">{{ pct(var95) }}</p>
            <p class="sub">历史模拟损失分位。</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card>
            <template #header>P1 已接通</template>
            <p>适当性：问卷 + 匹配 + 本地审计</p>
            <p>案例 2：批量回测 + Brinson + 报告</p>
            <p class="sub">演示规则，不是正式合规认定。</p>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import echarts from '../utils/echarts'
import { ElMessage } from 'element-plus'
import { getJson, withSource, num, pct, money } from '../api/client'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const payload = ref(null)
const chartEl = ref(null)
let chart

const data = computed(() => payload.value?.data || null)
const banner = computed(() => payload.value?.disclaimer || '演示系统：非实盘交易。')
const sourceLabel = computed(() => payload.value?.data_source || '—')
const var95 = computed(() => data.value?.risk?.var_cvar?.d1_95?.var)

function go(p) { router.push(p) }

function draw() {
  if (!chartEl.value || !data.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const rp = data.value.optimize.methods.risk_parity.nav
  const eq = data.value.optimize.methods.equal_weight.nav
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['风险平价', '等权'], textStyle: { color: '#8b9bb4' } },
    grid: { left: 40, right: 16, top: 32, bottom: 28 },
    xAxis: { type: 'category', data: rp.map((d) => d.date), axisLabel: { color: '#8b9bb4' } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b9bb4' }, splitLine: { lineStyle: { color: '#243049' } } },
    series: [
      { name: '风险平价', type: 'line', showSymbol: false, data: rp.map((d) => d.nav), lineStyle: { color: '#c9a227' } },
      { name: '等权', type: 'line', showSymbol: false, data: eq.map((d) => d.nav), lineStyle: { color: '#5b8ff9' } },
    ],
  })
}

function onResize() { chart?.resize() }

async function runCase() {
  loading.value = true
  error.value = ''
  try {
    const body = await getJson(withSource('/api/case1?capital=100000'))
    if (!body?.data?.optimize) throw new Error('案例 1 返回缺少组合结果')
    payload.value = body
    await nextTick()
    draw()
    ElMessage.success(`案例 1 完成 · 数据源 ${body.data_source}`)
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', onResize)
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>
