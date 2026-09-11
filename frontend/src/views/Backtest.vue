<template>
  <div class="page">
    <h2>策略回测</h2>
    <p class="sub">四种策略作用在股票池等权指数上；六指标 + 交易成本。样本内模拟。</p>
    <el-select v-model="strategy" style="width:200px;margin-right:8px">
      <el-option label="双均线" value="ma_cross" />
      <el-option label="均值回归" value="mean_reversion" />
      <el-option label="动量" value="momentum" />
      <el-option label="多因子合成" value="multi_factor" />
    </el-select>
    <el-button type="primary" data-testid="btn-backtest" :loading="loading" @click="load">运行回测</el-button>
    <el-button data-testid="btn-walk-forward" :loading="wfLoading" @click="loadWF">样本外滚动回测</el-button>
    <el-button data-testid="btn-open-case2" @click="$router.push('/case2')">打开案例 2 / 归因报告</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">{{ error }}</div>
    <template v-if="sel">
      <el-alert :title="payload.disclaimer" type="warning" :closable="false" show-icon style="margin-top:12px" />
      <div class="kpi-row">
        <div class="kpi"><div class="label">年化</div><div class="value">{{ pct(m.annual_return) }}</div></div>
        <div class="kpi"><div class="label">夏普</div><div class="value">{{ num(m.sharpe) }}</div></div>
        <div class="kpi"><div class="label">最大回撤</div><div class="value down">{{ pct(m.max_drawdown) }}</div></div>
        <div class="kpi"><div class="label">波动</div><div class="value">{{ pct(m.volatility) }}</div></div>
      </div>
      <div class="kpi-row">
        <div class="kpi"><div class="label">胜率</div><div class="value">{{ pct(m.win_rate) }}</div></div>
        <div class="kpi"><div class="label">卡玛</div><div class="value">{{ num(m.calmar) }}</div></div>
        <div class="kpi"><div class="label">交易次数</div><div class="value">{{ m.trades }}</div></div>
        <div class="kpi"><div class="label">成本</div><div class="value" style="font-size:16px">{{ pct(sel.cost, 2) }}</div></div>
      </div>
      <el-card>
        <template #header>{{ sel.label }} 净值</template>
        <div ref="chartEl" data-testid="chart-backtest" class="chart"></div>
      </el-card>
      <el-card style="margin-top:12px">
        <template #header>四策略对照</template>
        <el-table :data="allRows" size="small">
          <el-table-column prop="label" label="策略" />
          <el-table-column prop="annual_return" label="年化" />
          <el-table-column prop="sharpe" label="夏普" />
          <el-table-column prop="max_drawdown" label="最大回撤" />
          <el-table-column prop="volatility" label="波动" />
          <el-table-column prop="win_rate" label="胜率" />
          <el-table-column prop="calmar" label="卡玛" />
        </el-table>
      </el-card>
    </template>
    <template v-if="wfData">
      <el-alert :title="wfData.disclaimer" type="warning" :closable="false" show-icon style="margin-top:16px" />
      <h3 style="margin-top:12px">样本外滚动回测（Walk-Forward）</h3>
      <p class="sub">训练窗 {{ wfData.period.in_sample.start }} ~ {{ wfData.period.in_sample.end }}（{{ wfData.period.in_sample.n_days }} 天） → 测试窗 {{ wfData.period.out_of_sample.start }} ~ {{ wfData.period.out_of_sample.end }}（{{ wfData.period.out_of_sample.n_days }} 天）。权重在训练窗确定，测试窗不调参。不是收益承诺。</p>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card>
            <template #header>样本内（In-Sample）</template>
            <el-table :data="wfISRows" size="small">
              <el-table-column prop="label" label="方法" width="120" />
              <el-table-column prop="sharpe" label="夏普" />
              <el-table-column prop="annual_return" label="年化" />
              <el-table-column prop="max_drawdown" label="最大回撤" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>样本外（Out-of-Sample）</template>
            <el-table :data="wfOOSRows" size="small">
              <el-table-column prop="label" label="方法" width="120" />
              <el-table-column prop="sharpe" label="夏普" />
              <el-table-column prop="annual_return" label="年化" />
              <el-table-column prop="max_drawdown" label="最大回撤" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
      <el-card style="margin-top:12px">
        <template #header>IS vs OOS 净值对照（风险平价）</template>
        <div ref="wfChartEl" data-testid="chart-walk-forward" class="chart"></div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import echarts from '../utils/echarts'
import { ElMessage } from 'element-plus'
import { getJson, withSource, num, pct } from '../api/client'

const strategy = ref('multi_factor')
const loading = ref(false)
const error = ref('')
const payload = ref(null)
const chartEl = ref(null)
const wfLoading = ref(false)
const wfData = ref(null)
const wfChartEl = ref(null)
let chart
let wfChart
const sel = computed(() => payload.value?.data?.selected)
const m = computed(() => sel.value?.metrics || {})
const allRows = computed(() => (payload.value?.data?.all?.strategies || []).map((s) => ({
  label: s.label,
  annual_return: pct(s.metrics.annual_return),
  sharpe: num(s.metrics.sharpe),
  max_drawdown: pct(s.metrics.max_drawdown),
  volatility: pct(s.metrics.volatility),
  win_rate: pct(s.metrics.win_rate),
  calmar: num(s.metrics.calmar),
})))

function draw() {
  if (!chartEl.value || !sel.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const nav = sel.value.nav || []
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 28 },
    xAxis: { type: 'category', data: nav.map((d) => d.date), axisLabel: { color: '#8b9bb4' } },
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b9bb4' }, splitLine: { lineStyle: { color: '#243049' } } },
    series: [{ type: 'line', showSymbol: false, data: nav.map((d) => d.nav), lineStyle: { color: '#3ecf8e' } }],
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await getJson(withSource(`/api/backtest?strategy=${strategy.value}`))
    await nextTick()
    draw()
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)

const wfISRows = computed(() => {
  if (!wfData.value) return []
  const is = wfData.value.in_sample
  return [
    { label: '风险平价', ...is.risk_parity.metrics },
    { label: '等权', ...is.equal_weight.metrics },
    { label: '基准指数', ...is.benchmark.metrics },
  ].map((r) => ({ label: r.label, sharpe: num(r.sharpe), annual_return: pct(r.annual_return), max_drawdown: pct(r.max_drawdown) }))
})

const wfOOSRows = computed(() => {
  if (!wfData.value) return []
  const oos = wfData.value.out_of_sample
  return [
    { label: '风险平价', ...oos.risk_parity.metrics },
    { label: '等权', ...oos.equal_weight.metrics },
    { label: '基准指数', ...oos.benchmark.metrics },
  ].map((r) => ({ label: r.label, sharpe: num(r.sharpe), annual_return: pct(r.annual_return), max_drawdown: pct(r.max_drawdown) }))
})

function drawWF() {
  if (!wfChartEl.value || !wfData.value) return
  if (!wfChart) wfChart = echarts.init(wfChartEl.value)
  const isNav = wfData.value.in_sample.risk_parity.nav || []
  const oosNav = wfData.value.out_of_sample.risk_parity.nav || []
  wfChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['样本内', '样本外'], textStyle: { color: '#8b9bb4' } },
    grid: { left: 40, right: 16, top: 32, bottom: 28 },
    xAxis: [
      { type: 'category', data: isNav.map((d) => d.date), axisLabel: { color: '#8b9bb4' } },
    ],
    yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b9bb4' }, splitLine: { lineStyle: { color: '#243049' } } },
    series: [
      { name: '样本内', type: 'line', showSymbol: false, data: isNav.map((d) => d.nav), lineStyle: { color: '#3ecf8e' } },
      { name: '样本外', type: 'line', showSymbol: false, data: oosNav.map((d) => d.nav), lineStyle: { color: '#f0a020' } },
    ],
  })
}

async function loadWF() {
  wfLoading.value = true
  try {
    const body = await getJson(withSource('/api/backtest/walk-forward'))
    wfData.value = body.data
    await nextTick()
    drawWF()
  } catch (e) {
    ElMessage.error(e.message || String(e))
  } finally {
    wfLoading.value = false
  }
}
</script>
