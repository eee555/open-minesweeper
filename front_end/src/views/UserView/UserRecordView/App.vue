<template>
    <div class="user-record-view">
        <SaoleiCard :user-id="store.player.id" />
        <ThrpCard :user-id="store.player.id" />
        <ElSkeleton v-show="loading" animated style="margin-top: 0px;" :rows="8" />
        <PLuckCard :records="pluckRecords" />
    </div>
</template>

<script lang="ts" setup>

import { ElMessage, ElSkeleton } from 'element-plus';
import { nextTick, ref } from 'vue';

import PLuckCard from './PLuckCard.vue';
import SaoleiCard from './SaoleiCard.vue';
import ThrpCard from './ThrpCard.vue';

import type { CustomPluckRecord } from '@/services/msuserService';
import { fetchCustomPluckPlayerRecords } from '@/services/msuserService';
import { store } from '@/store';

const loading = ref(true);
const pluckRecords = ref<CustomPluckRecord[]>([]);

// 此处和父组件配合，等一下从store里获取用户的id
void nextTick(() => {
    const playerId = store.player.id;
    void fetchCustomPluckPlayerRecords(playerId).then((data) => {
        pluckRecords.value = data;
    }).catch(() => {
        ElMessage.error({ message: '自定义密度纪录加载失败', offset: 68 });
    }).finally(() => {
        loading.value = false;
    });
});
</script>

<style scoped>
.user-record-view {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
</style>
