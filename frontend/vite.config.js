import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 组件按需注册：模板中用到的 el-* 才会打进产物，
    // 替代 app.use(ElementPlus) 全量注册（JS 体积 814KB -> 数十 KB）。
    Components({
      resolvers: [ElementPlusResolver({ importStyle: false })],
      dts: false,
    }),
  ],
  build: {
    // 分包：echarts / element-plus / vue 全家桶 / 业务代码 各自独立 chunk。
    // 配合按需注册的 echarts，主业务包显著变小；vendor 包可被浏览器长期缓存。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts')) return 'echarts'
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
            if (
              id.includes('/vue/') ||
              id.includes('vue-router') ||
              id.includes('@vue/')
            ) {
              return 'vue-vendor'
            }
            return 'vendor'
          }
          return undefined
        },
      },
    },
    // 静态资产按需内联阈值：低于该字节数的资产转 base64，减少请求数
    assetsInlineLimit: 4096,
  },
  server: {
    host: 'localhost',
    port: 3000,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
      '/health': 'http://127.0.0.1:8010',
      '/docs': 'http://127.0.0.1:8010',
      '/openapi.json': 'http://127.0.0.1:8010',
    },
  },
})
