<template>
  <div class="page">
    <h2>因子增强选股</h2>
    <p class="sub">≥10 因子截面标准化，IC/IR 动态加权，衰减告警。{{ extra }}</p>
    <el-button type="primary" data-testid="btn-screen" :loading="loading" @click="load">刷新选股</el-button>
    <div v-if="error" class="placeholder-box" style="margin-top:12px">{{ error }}</div>
    <template v-if="d">
      <el-alert :title="disclaimer" type="warning" :closable="false" show-icon style="margin-top:12px" />
      <div class="kpi-row">
        <div class="kpi"><div class="label">因子数</div><div class="value">{{ d.factor_count }}</div></div>
        <div class="kpi"><div class="label">加权方式</div><div class="value" style="font-size:16px">{{ d.diagnostics.weight_mode }}</div></div>
        <div class="kpi"><div class="label">衰减告警</div><div class="value" :class="d.diagnostics.decay_alerts.length ? 'down' : 'up'">{{ d.diagnostics.decay_alerts.length }}</div></div>
        <div class="kpi"><div class="label">截面日期</div><div class="value" style="font-size:16px">{{ d.asof }}</div></div>
      </div>
      <el-card>
        <template #header>动态权重（IR&gt;0 归一）</template>
        <el-table :data="weightRows" size="small" max-height="240">
          <el-table-column prop="label" label="因子" />
          <el-table-column prop="mean_ic" label="IC均值" />
          <el-table-column prop="ir" label="IR" />
          <el-table-column prop="weight" label="权重" />
        </el-table>
      </el-card>
      <el-card style="margin-top:12px">
        <template #header>衰减检测</template>
        <div v-if="!d.diagnostics.decay_alerts.length" class="placeholder-box">当前窗口未触发衰减告警。</div>
        <el-table v-else :data="d.diagnostics.decay_alerts" size="small">
          <el-table-column prop="label" label="因子" />
          <el-table-column prop="message" label="说明" />
          <el-table-column prop="recent_ic" label="近窗IC" />
        </el-table>
      </el-card>
      <el-card style="margin-top:12px">
        <template #header>股票池评分</template>
        <el-table :data="d.universe_scored" size="small" max-height="420">
          <el-table-column prop="rank" label="#" width="50" />
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="sector" label="行业" width="80" />
          <el-table-column prop="composite" label="综合分">
            <template #default="{ row }">{{ num(row.composite) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getJson, withSource, num } from '../api/client'

const loading = ref(false)
const error = ref('')
const payload = ref(null)
const d = computed(() => payload.value?.data || null)
const disclaimer = computed(() => payload.value?.disclaimer || '')
const extra = computed(() => payload.value ? `数据源 ${payload.value.data_source}` : '')

const weightRows = computed(() => {
  if (!d.value) return []
  const ic = d.value.diagnostics.ic
  const w = d.value.diagnostics.dynamic_weights
  return Object.keys(w).map((k) => ({
    id: k,
    label: ic[k]?.label || k,
    mean_ic: num(ic[k]?.mean_ic, 3),
    ir: num(ic[k]?.ir, 3),
    weight: num(w[k], 3),
  }))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    payload.value = await getJson(withSource('/api/screen'))
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
