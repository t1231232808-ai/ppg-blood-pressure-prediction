<template>
  <router-view v-if="$route.path === '/login' || $route.path === '/prediction' || $route.path === '/result' || $route.path === '/records' || $route.path === '/admin' || $route.path.startsWith('/prediction/')" />
  <el-container v-else class="app-shell">
    <el-aside width="220px" class="sidebar">
      <div class="brand">PPG 血压预测</div>
      <el-menu router :default-active="$route.path" class="nav-menu">
        <el-menu-item index="/prediction">PPG信号上传</el-menu-item>
        <el-menu-item index="/result">实时预测</el-menu-item>
        <el-menu-item index="/records">历史记录</el-menu-item>
        <el-menu-item index="/admin">系统配置</el-menu-item>
        <el-menu-item index="/login">登录注册</el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>
