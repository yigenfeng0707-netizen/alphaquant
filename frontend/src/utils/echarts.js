// ECharts 按需引入：仅注册本项目用到的图表与组件，显著减小打包体积。
// 使用方式与完整版一致：
//   import * as echarts from '../utils/echarts'
//   const chart = echarts.init(el); chart.setOption({...})
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  // charts
  BarChart,
  LineChart,
  PieChart,
  // components
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  // renderers
  CanvasRenderer,
])

export default echarts