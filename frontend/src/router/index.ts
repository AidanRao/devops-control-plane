import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'
import AgentDetail from '@/views/AgentDetail.vue'

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: Dashboard,
    },
    {
      path: '/agents/:deviceId',
      name: 'agent-detail',
      component: AgentDetail,
      props: true,
    },
  ],
})

export default router
