<script setup lang="ts">
import AgentTable from '@/components/AgentTable.vue'
import logoUrl from '/logo.png?url'
</script>

<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <img :src="logoUrl" alt="logo" class="logo" />
      <h1>DevOps 控制台</h1>
    </header>
    <main class="dashboard-body">
      <section class="panel">
        <div class="panel-title">在线 Agent</div>
        <AgentTable />
      </section>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100%;
  padding: 24px;
  box-sizing: border-box;
}
.dashboard-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.logo {
  width: 32px;
  height: 32px;
}
.dashboard-header h1 {
  margin: 0;
  font-size: 20px;
  color: #1f2937;
}
.panel {
  margin-bottom: 20px;
}
.panel-title {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}
</style>
