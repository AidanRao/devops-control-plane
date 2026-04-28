import axios from 'axios'

// 开发环境走 Vite proxy，生产环境同源部署
const http = axios.create({
  baseURL: '/',
  timeout: 15000,
})

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    // 统一错误透传，具体处理交给调用方
    return Promise.reject(error)
  },
)

export default http
