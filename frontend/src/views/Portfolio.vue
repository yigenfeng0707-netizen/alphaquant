<template>
  <div class="page">
    <h2>组合优化</h2>
    <p class="sub">等权 / 风险平价 / 最小方差 / 最大夏普。风险平价为 SciPy 等风险贡献。</p>
    <el-button type="primary" data-testid="btn-optimize" :loading="loading" @click="load">优化入选篮子</el-button>
    <el-button data-testid="btn-brinson" :loading="attrLoading" @click="loadAttr">加载 Brinson 归因</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">{{ error }}</div>
    <template v-if="methods">
      <el-alert :title="payload.disclaimer" type="warning" :closable="false" show-icon style="margin-top:12px" />
      <div class="kpi-row">
        <div class="kpi"><div class="label">风险平价夏普</div><div class="value up">{{ num(d.sharpe_rp) }}</div></div>
        <div class="kpi"><div class="label">等权夏普</div><div class="value">{{ num(d.sharpe_eq) }}</div></div>
        <div class="kpi"><div class="label">平价是否更优</div><div class="value" :class="d.sharpe_rp_better ? 'up' : 'down'">{{ d.sharpe_rp_better ? '是' : '否' }}</div></div>
        <div class="kpi"><div class="label">方法数</div><div class="value">4</div></div>
      </div>
      <el-radio-group v-model="method" style="margin-bottom:12px">
        <el-radio-button v-for="k in keys" :key="k" :value="k">{{ methods[k].label }}</el-radio-button>
      </el-radio-group>
      <el-row :gutter="16">
        <el-col :span="10">
          <el-card>
            <template #header>权重</template>
            <div ref="pieEl" class="chart"></div>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card>
            <template #header>明细</template>
            <el-table :data="methods[method].weights" size="small" max-height="320">
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="code" label="代码" width="90" />
              <el-table-column label="权重">
                <template #default="{ row }">{{ pct(row.weight) }}</template>
              </el-table-column>
              <el-table-column label="风险贡献">
                <template #default="{ row }">{{ pct(row.risk_contrib) }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
      <el-card style="margin-top:12px">
        <template #header>四方法样本内指标</template>
        <el-table :data="cmpRows" size="small">
          <el-table-column prop="label" label="方法" />
          <el-table-column prop="sharpe" label="夏普" />
          <el-table-column prop="annual_return" label="年化" />
          <el-table-column prop="max_drawdown" label="最大回撤" />
          <el-table-column prop="volatility" label="波动" />
        </el-table>
      </el-card>
      <el-card style="margin-top:12px" data-testid="card-brinson">
        <template #header>Brinson 归因（相对等权篮子）</template>
        <div v-if="attrError" class="placeholder-box">{{ attrError }}</div>
        <template v-else-if="attr">
          <div class="kpi-row">
            <div class="kpi"><div class="label">配置</div><div class="value">{{ pct(attr.allocation) }}</div></div>
            <div class="kpi"><div class="label">选择</div><div class="value">{{ pct(attr.selection) }}</div></div>
            <div class="kpi"><div class="label">交互</div><div class="value">{{ pct(attr.interaction) }}</div></div>
            <div class="kpi"><div class="label">超额</div><div class="value">{{ pct(attr.excess_return) }}</div></div>
          </div>
          <p class="sub" data-testid="brinson-explain">{{ attr.explain }}</p>
          <el-table :data="attr.sectors" size="small">
            <el-table-column prop="sector" label="行业" />
            <el-table-column label="配置"><template #default="{ row }">{{ pct(row.allocation) }}</template></el-table-column>
            <el-table-column label="选择"><template #default="{ row }">{{ pct(row.selection) }}</template></el-table-column>
            <el-table-column label="交互"><template #default="{ row }">{{ pct(row.interaction) }}</template></el-table-column>
          </el-table>
        </template>
        <div v-else-if="attrLoading" class="placeholder-box">正在计算 Brinson 归因…</div>
        <div v-else class="placeholder-box">点击「加载 Brinson 归因」查看配置/选择效应。</div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getJson, withSource, num, pct } from '../api/client'

const loading = ref(false)
const attrLoading = ref(false)
const error = ref('')
const attrError = ref('')
const attr = ref(null)
const payload = ref(null)
const method = ref('risk_parity')
const pieEl = ref(null)
let pie
const d = computed(() => payload.value?.data)
const methods = computed(() => d.value?.methods)
const keys = ['equal_weight', 'risk_parity', 'min_variance', 'max_sharpe']
const cmpRows = computed(() => keys.map((k) => {
  const x = methods.value?.[k]
  return {
    label: x?.label,
    sharpe: num(x?.metrics?.sharpe),
    annual_return: pct(x?.metrics?.annual_return),
    max_drawdown: pct(x?.metrics?.max_drawdown),
    volatility: pct(x?.metrics?.volatility),
  }
}))

function drawPie() {
  if (!pieEl.value || !methods.value) return
  if (!pie) pie = echarts.init(pieEl.value)
  const w = methods.value[method.value].weights
  pie.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['36%', '64%'],
      data: w.map((r) => ({ name: r.name, value: r.weight })),
      label: { color: '#e8eef7' },
    }],
  })
}

watch(method, () => drawPie())

async function load() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await getJson(withSource('/api/optimize'))
    await nextTick()
    drawPie()
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

async function loadAttr() {
  attrLoading.value = true
  attrError.value = ''
  try {
    const body = await getJson(withSource('/api/attribution/brinson?method=risk_parity'))
    if (body.implemented !== true) throw new Error('Brinson 仍为占位')
    if (body.data?.allocation === undefined) throw new Error('归因缺少配置效应')
    attr.value = body.data
    ElMessage.success('Brinson 已加载')
  } catch (e) {
    attrError.value = e.message || String(e)
    ElMessage.error(attrError.value)
  } finally {
    attrLoading.value = false
  }
}

onMounted(async () => {
  await load()
  await loadAttr()
})
</script>
