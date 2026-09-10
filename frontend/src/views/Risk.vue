<template>
  <div class="page">
    <h2>风险监控</h2>
    <p class="sub">三种 VaR 方法对比（历史模拟 / 参数法 / 蒙特卡洛）+ 压力测试。非监管报备口径。</p>
    <el-button type="primary" data-testid="btn-risk" :loading="loading" @click="load">评估风险平价组合</el-button>
    <el-button data-testid="btn-open-suitability" @click="$router.push('/suitability')">打开适当性问卷</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">{{ error }}</div>
    <template v-if="r">
      <el-alert :title="payload.disclaimer" type="warning" :closable="false" show-icon style="margin-top:12px" />
      <div class="kpi-row">
        <div class="kpi"><div class="label">95% VaR（日）</div><div class="value down">{{ pct(r.var_cvar.d1_95.var) }}</div></div>
        <div class="kpi"><div class="label">95% CVaR（日）</div><div class="value down">{{ pct(r.var_cvar.d1_95.cvar) }}</div></div>
        <div class="kpi"><div class="label">99% VaR（日）</div><div class="value down">{{ pct(r.var_cvar.d1_99.var) }}</div></div>
        <div class="kpi"><div class="label">样本天数</div><div class="value">{{ r.var_cvar.d1_95.n }}</div></div>
      </div>
      <el-card v-if="mc" style="margin-top:12px" data-testid="card-var-comparison">
        <template #header>三种 VaR 方法对比</template>
        <el-table :data="varCmpRows" size="small">
          <el-table-column prop="method" label="方法" width="120" />
          <el-table-column label="95% VaR"><template #default="{ row }">{{ pct(row.var95) }}</template></el-table-column>
          <el-table-column label="95% CVaR"><template #default="{ row }">{{ pct(row.cvar95) }}</template></el-table-column>
          <el-table-column label="99% VaR"><template #default="{ row }">{{ pct(row.var99) }}</template></el-table-column>
          <el-table-column label="99% CVaR"><template #default="{ row }">{{ pct(row.cvar99) }}</template></el-table-column>
        </el-table>
        <p class="sub" style="margin-top:8px">{{ r.note }}</p>
      </el-card>
      <el-card>
        <template #header>压力测试</template>
        <el-table :data="r.stress" size="small">
          <el-table-column prop="label" label="情景" />
          <el-table-column prop="type" label="类型" width="140" />
          <el-table-column label="损失">
            <template #default="{ row }">{{ pct(row.loss) }}</template>
          </el-table-column>
          <el-table-column prop="start" label="起" />
          <el-table-column prop="end" label="止" />
        </el-table>
      </el-card>
      <div class="placeholder-box" style="margin-top:12px">适当性已在「适当性」页实现（问卷 + 匹配 + 本地审计）。本页风控数字为历史模拟/参数法/蒙特卡洛三种方法对比，不是监管报备口径。</div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getJson, withSource, pct } from '../api/client'

const loading = ref(false)
const error = ref('')
const payload = ref(null)
const r = computed(() => payload.value?.data)
const mc = computed(() => r.value?.methods_comparison)
const varCmpRows = computed(() => {
  if (!mc.value) return []
  const labels = { historical: '历史模拟', parametric: '参数法', montecarlo: '蒙特卡洛' }
  return Object.entries(mc.value).map(([key, val]) => ({
    method: labels[key] || key,
    var95: val.d1_95?.var,
    cvar95: val.d1_95?.cvar,
    var99: val.d1_99?.var,
    cvar99: val.d1_99?.cvar,
  }))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await getJson(withSource('/api/risk?method=risk_parity'))
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
