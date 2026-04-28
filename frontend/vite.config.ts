import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

// 后端端口与 .env 中 PORT 保持一致
const BACKEND_PORT = process.env.BACKEND_PORT || '8002'
const BACKEND_TARGET = `http://127.0.0.1:${BACKEND_PORT}`

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  // 生产构建时资源通过 FastAPI 的 /static/ 静态挂载访问
  base: '/static/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: BACKEND_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: BACKEND_TARGET.replace('http', 'ws'),
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    // 构建产物输出到 FastAPI 的静态目录，由 /ui 直接托管 index.html，/static 托管 assets
    outDir: path.resolve(__dirname, '../app/static'),
    emptyOutDir: true,
    assetsDir: 'assets',
  },
})
