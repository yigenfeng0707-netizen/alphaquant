<template>
  <div class="page">
    <h2>投资适当性（演示）</h2>
    <p class="sub">问卷分档保守 / 稳健 / 平衡 / 积极 / 进取，并与风险平价、仓位、波动约束匹配。不采集身份证号。</p>
    <el-alert title="本地演示规则，不是正式合格投资者认定或投资建议。" type="warning" :closable="false" show-icon />
    <div style="margin-bottom:12px">
      <el-button data-testid="btn-preset-conservative" @click="applyPreset('conservative')">填入保守示例</el-button>
      <el-button data-testid="btn-preset-balanced" @click="applyPreset('balanced')">填入平衡示例</el-button>
      <el-button data-testid="btn-preset-aggressive" @click="applyPreset('aggressive')">填入进取示例</el-button>
      <el-select v-model="method" style="width:160px;margin:0 8px">
        <el-option label="风险平价" value="risk_parity" />
        <el-option label="最小方差" value="min_variance" />
        <el-option label="等权" value="equal_weight" />
        <el-option label="最大夏普" value="max_sharpe" />
      </el-select>
      <el-button type="primary" data-testid="btn-suitability-submit" :loading="loading" @click="submit">提交问卷并匹配</el-button>
    </div>
    <div v-if="error" class="placeholder-box">{{ error }}</div>
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card v-for="q in questions" :key="q.id" style="margin-bottom:10px">
          <template #header>{{ q.title }}</template>
          <el-radio-group v-model="answers[q.id]">
            <el-radio v-for="o in q.options" :key="o.value" :value="o.value">{{ o.label }}</el-radio>
          </el-radio-group>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card v-if="result">
          <template #header>匹配结果</template>
          <div class="kpi-row" style="grid-template-columns:1fr 1fr">
            <div class="kpi"><div class="label">得分</div><div class="value">{{ result.score }}</div></div>
            <div class="kpi"><div class="label">分档</div><div class="value" style="font-size:18px">{{ result.profile_label }}</div></div>
          </div>
          <el-tag :type="tagType" size="large">{{ result.match?.decision }}</el-tag>
          <p class="sub">拟配置方法：{{ result.match?.method_label }} · 建议：{{ result.match?.suggested_method_label }}</p>
          <el-alert
            v-if="result.match?.blocked"
            title="匹配拦截：当前组合不适合该风险档，演示流程应停止或改方法/降仓。"
            type="error"
            :closable="false"
            style="margin:8px 0"
          />
          <ul>
            <li v-for="(r, i) in result.match?.reasons || []" :key="i">{{ r }}</li>
          </ul>
          <p class="sub">{{ result.match?.rule_note }}</p>
          <p class="sub">样本内波动 {{ pct(result.metrics?.volatility) }} · 回撤 {{ pct(result.metrics?.max_drawdown) }}</p>
        </el-card>
        <el-card style="margin-top:12px">
          <template #header>审计日志（本地 JSONL）</template>
          <p class="sub">仅时间、答案摘要、匹配结果。不含证件。</p>
          <el-table :data="logs" size="small" max-height="280" data-testid="table-audit">
            <el-table-column prop="ts" label="时间" width="150" />
            <el-table-column prop="profile_label" label="分档" width="70" />
            <el-table-column prop="decision" label="结论" width="70" />
            <el-table-column prop="answers_summary" label="摘要" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getJson, postJson, withSource, pct } from '../api/client'

const loading = ref(false)
const error = ref('')
const method = ref('risk_parity')
const questions = ref([])
const answers = reactive({})
const result = ref(null)
const logs = ref([])

const tagType = computed(() => {
  const d = result.value?.match?.decision
  if (d === '拦截') return 'danger'
  if (d === '警告') return 'warning'
  return 'success'
})

function applyPreset(key) {
  const map = {
    conservative: { q1: 1, q2: 2, q3: 1, q4: 1, q5: 1, q6: 1, q7: 2, q8: 1 },
    balanced: { q1: 3, q2: 3, q3: 3, q4: 3, q5: 3, q6: 3, q7: 3, q8: 3 },
    aggressive: { q1: 5, q2: 5, q3: 5, q4: 5, q5: 5, q6: 5, q7: 5, q8: 5 },
  }
  const src = map[key]
  if (!src) return
  Object.assign(answers, src)
  ElMessage.info(key === 'conservative' ? '已填入保守档（对风险平价满仓通常会拦截）' : '已填入示例答案')
}

async function load() {
  error.value = ''
  try {
    const body = await getJson(withSource('/api/suitability'))
    if (body.implemented !== true) throw new Error('适当性接口仍为占位')
        questions.value = body.questionnaire?.questions || []
        applyPreset('balanced')
        logs.value = body.recent_logs || []
        result.value = null
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  }
}

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const body = await postJson('/api/suitability/evaluate', {
      answers: { ...answers },
      source: localStorage.getItem('aq_source') || 'offline',
      method: method.value,
      session_label: '本地演示',
    })
    if (body.implemented !== true || !body.data?.match) throw new Error('适当性返回不完整')
    result.value = body.data
    logs.value = [{ ...(body.data.audit || {}), ts: body.data.audit?.ts }, ...logs.value].slice(0, 20)
    const d = body.data.match.decision
    if (body.data.match.blocked) ElMessage.error(`匹配${d}`)
    else ElMessage.success(`匹配${d} · ${body.data.profile_label}`)
  } catch (e) {
    error.value = e.message || String(e)
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
