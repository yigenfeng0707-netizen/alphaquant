<template>
  <div class="page">
    <h2>案例 2 · 小型私募研究流程（演示口径）</h2>
    <p class="sub">批量回测四策略 + Brinson 归因 + 标准化风控报告。名义本金 1 亿元仅为机构场景演示，不是已管理实盘规模。</p>
    <el-alert title="演示口径：不是真实持仓、不是托管估值、不是收益承诺。" type="warning" :closable="false" show-icon />
    <el-button type="primary" data-testid="btn-case2-run" :loading="loading" @click="run">运行案例 2 批量回测</el-button>
    <el-button data-testid="btn-export-report" :loading="exporting" @click="exportReport">生成并导出风控报告</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">{{ error }}</div>
    <template v-if="d">
      <div class="kpi-row">
        <div class="kpi"><div class="label">名义本金</div><div class="value" style="font-size:16px">{{ d.notional?.label }}</div></div>
        <div class="kpi"><div class="label">配置效应</div><div class="value">{{ pct(d.brinson?.allocation) }}</div></div>
        <div class="kpi"><div class="label">选择效应</div><div class="value">{{ pct(d.brinson?.selection) }}</div></div>
        <div class="kpi"><div class="label">超额（对等权）</div><div class="value">{{ pct(d.brinson?.excess_return) }}</div></div>
      </div>
      <el-card>
        <template #header>四策略批量回测（样本内）</template>
        <el-table :data="scaledRows" size="small" data-testid="table-case2-batch">
          <el-table-column prop="label" label="策略" />
          <el-table-column prop="annual_return" label="年化" />
          <el-table-column prop="sharpe" label="夏普" />
          <el-table-column prop="max_drawdown" label="最大回撤" />
          <el-table-column prop="notional_end" label="名义期末" />
        </el-table>
      </el-card>
      <el-row :gutter="16" style="margin-top:12px">
        <el-col :span="12">
          <el-card>
            <template #header>Brinson 瀑布（配置 / 选择 / 交互）</template>
            <div ref="chartEl" data-testid="chart-brinson" class="chart"></div>
            <p class="sub">{{ d.brinson?.explain }}</p>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>分行业归因</template>
            <el-table :data="d.brinson?.sectors || []" size="small" max-height="280">
              <el-table-column prop="sector" label="行业" width="80" />
              <el-table-column label="配置"><template #default="{ row }">{{ pct(row.allocation) }}</template></el-table-column>
              <el-table-column label="选择"><template #default="{ row }">{{ pct(row.selection) }}</template></el-table-column>
              <el-table-column label="交互"><template #default="{ row }">{{ pct(row.interaction) }}</template></el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
      <el-card style="margin-top:12px">
        <template #header>标准化风控报告（结构化）</template>
        <p>95% VaR：{{ pct(d.report?.var_cvar?.d1_95?.var) }} · CVaR：{{ pct(d.report?.var_cvar?.d1_95?.cvar) }}</p>
        <el-table :data="d.report?.stress || []" size="small">
          <el-table-column prop="label" label="情景" />
          <el-table-column label="损失"><template #default="{ row }">{{ pct(row.loss) }}</template></el-table-column>
        </el-table>
        <p v-if="exportPath" class="sub" data-testid="export-path">已导出：{{ exportPath }}</p>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import echarts from '../utils/echarts'
import { ElMessage } from 'element-plus'
import { getJson, postJson, withSource, num, pct, money } from '../api/client'

const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const payload = ref(null)
const exportPath = ref('')
const chartEl = ref(null)
let chart
const d = computed(() => payload.value?.data)
const scaledRows = computed(() => (d.value?.scaled || []).map((s) => ({
  label: s.label,
  annual_return: pct(s.metrics?.annual_return),
  sharpe: num(s.metrics?.sharpe),
  max_drawdown: pct(s.metrics?.max_drawdown),
  notional_end: money(s.notional_end),
})))

function draw() {
  if (!chartEl.value || !d.value?.brinson) return
  if (!chart) chart = echarts.init(chartEl.value)
  const b = d.value.brinson
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 16, top: 16, bottom: 28 },
    xAxis: { type: 'category', data: ['配置', '选择', '交互', '超额'], axisLabel: { color: '#8b9bb4' } },
    yAxis: { type: 'value', axisLabel: { color: '#8b9bb4', formatter: (v) => `${(v * 100).toFixed(1)}%` }, splitLine: { lineStyle: { color: '#243049' } } },
    series: [{
      type: 'bar',
      data: [b.allocation, b.selection, b.interaction, b.excess_return],
      itemStyle: { color: '#c9a227' },
    }],
  })
}

function onResize() { chart?.resize() }

async function run() {
  loading.value = true
  error.value = ''
  try {
    const body = await getJson(withSource('/api/case2?notional=100000000'))
    if (body.implemented !== true) throw new Error('案例 2 仍为占位')
    if (!body.data?.brinson || !body.data?.report) throw new Error('案例 2 缺少归因或报告')
    payload.value = body
    await nextTick()
    draw()
    ElMessage.success('案例 2 完成（演示口径）')
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

async function exportReport() {
  exporting.value = true
  try {
    const body = await postJson('/api/case2/export', {
      source: localStorage.getItem('aq_source') || 'offline',
      fmt: 'md',
      notional: 100000000,
    })
    if (body.implemented !== true || !body.data?.export?.path) throw new Error('导出失败')
    payload.value = body
    exportPath.value = body.data.export.path
    await nextTick()
    draw()
    ElMessage.success(`已写入 ${body.data.export.filename}`)
  } catch (e) {
    ElMessage.error(e.message || String(e))
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  run()
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>
