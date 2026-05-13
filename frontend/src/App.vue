<template>
  <div class="app-container">
    <el-menu mode="horizontal" background-color="#131722" text-color="#d1d4dc" router>
      <el-menu-item index="/">📈 量化回测总览</el-menu-item>
      <el-menu-item index="/config">⚙️ 配置管理</el-menu-item>
      <el-menu-item index="/mx">🧠 妙想工具箱</el-menu-item>
      <el-menu-item index="/research/alpha">🧪 Alpha 研究</el-menu-item>
    </el-menu>
    <router-view></router-view>
  </div>
</template>

<style>
body {
  margin: 0;
  font-family: sans-serif;
  background-color: #0b0e14;
  color: #d1d4dc;
}

.app-container {
  min-height: 100vh;
  background: #0b0e14;
}

.el-menu {
  border-bottom: 1px solid #2b3139 !important;
  background: #131722 !important;
}

.el-menu--horizontal > .el-menu-item {
  color: #d1d4dc !important;
  background: #131722 !important;
}

.el-menu--horizontal > .el-menu-item.is-active {
  color: #fff !important;
  border-bottom-color: #0ECB81 !important;
}
</style>
