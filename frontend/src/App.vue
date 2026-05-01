<template>
  <div class="app-container">
    <el-menu mode="horizontal" background-color="#131722" text-color="#d1d4dc" router>
      <el-menu-item index="/">📈 量化回测总览</el-menu-item>
      <el-menu-item index="/config">⚙️ 配置管理</el-menu-item>
      <el-menu-item index="/mx">🧠 妙想工具箱</el-menu-item>
    </el-menu>
    <router-view></router-view>
  </div>
</template>

<style>
body { margin: 0; font-family: sans-serif; background-color: #0b0e14; color: #d1d4dc; }
.app-container { min-height: 100vh; background: #0b0e14; }
.el-menu { border-bottom: 1px solid #2b3139 !important; background: #131722 !important; }
.el-menu--horizontal > .el-menu-item { color: #d1d4dc !important; background: #131722 !important; }
.el-menu--horizontal > .el-menu-item.is-active { color: #fff !important; border-bottom-color: #0ECB81 !important; }
.el-card { background: #131722 !important; border-color: #2b3139 !important; color: #d1d4dc !important; }
.el-card__header, .el-card__body { background: #131722 !important; color: #d1d4dc !important; }
.el-table { background: #1a1e29 !important; }
.el-table th.el-table__cell, .el-table td.el-table__cell { background: #1a1e29 !important; color: #eef2f7 !important; }
.el-table .cell { color: #eef2f7 !important; }
.el-table .el-table__header-wrapper,
.el-table .el-table__body-wrapper,
.el-table .el-table__fixed,
.el-table .el-table__fixed-right,
.el-table .el-table__inner-wrapper,
.el-table .el-table__inner-wrapper::before,
.el-scrollbar,
.el-scrollbar__wrap,
.el-scrollbar__view { background: #1a1e29 !important; }
.el-table .el-table__body .el-table__row td,
.el-table .el-table__body .el-table__row > td { background: #1a1e29 !important; color: #eef2f7 !important; }
.el-table .el-table__body .el-table__row:hover > td { background: #222836 !important; }
.el-table__empty-block, .el-table__empty-text { background: #1a1e29 !important; color: #8a919e !important; }
</style>
