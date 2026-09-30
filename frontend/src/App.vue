<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">城市地下管网巡检养护平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向城市给排水与燃气管网的管段建档、检查井阀门、巡查巡检、内窥检测、缺陷修复与压力流量监测的一体化养护后台。</span>
        <span class="head-user">
          当前身份：
          <select
            v-if="store.operators.length"
            class="operator-select"
            :value="store.operator?.id"
            @change="onSwitch(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="op in store.operators" :key="op.id" :value="op.id">
              {{ op.姓名 }}（{{ op.角色 }} · {{ op.所属班组 }}）
            </option>
          </select>
          <template v-else>{{ store.operator?.姓名 ?? '未登录' }}</template>
          · {{ store.shiftLabel }}
        </span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

onMounted(() => {
  void store.loadOperators()
})

function onSwitch(value: string) {
  store.switchOperator(Number(value))
  // 身份变化后重新拉取当前页数据：路由视图自行监听 store.operator 即可，这里直接整页刷新最省事且可预期。
  window.location.reload()
}

const navItems = [{ label: "运营概览", path: "/" }, { label: "班组工作台", path: "/workbench" }, { label: "资质培训台账", path: "/training" }, { label: "管段档案", path: "/pipe" }, { label: "检查井", path: "/manhole" }, { label: "阀门井室", path: "/valve" }, { label: "泵站设施", path: "/pumpstation" }, { label: "巡查任务", path: "/patrol" }, { label: "缺陷登记", path: "/defect" }, { label: "内窥检测", path: "/cctv" }, { label: "修复施工", path: "/repair" }, { label: "压力监测", path: "/pressure" }, { label: "流量监测", path: "/flow" }, { label: "泄漏排查", path: "/leak" }, { label: "清淤疏浚", path: "/dredge" }, { label: "养护材料", path: "/material" }, { label: "养护机械", path: "/equip" }, { label: "占道许可", path: "/traffic" }, { label: "公众诉求", path: "/complaint" }, { label: "养护资金", path: "/fund" }, { label: "管网档案", path: "/archive" }]
</script>

<style scoped>
.operator-select {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 13px;
}
</style>
