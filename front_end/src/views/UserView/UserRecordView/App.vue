<template>
    <MasonryLayout class="user-record-view" :minimum-column-width="400">
        <div data-record-item="saolei">
            <SaoleiCard :user-id="store.player.id" />
        </div>
        <div data-record-item="strict-ng">
            <StrictNgCard :user-id="store.player.id" />
        </div>
        <div data-record-item="path">
            <PathCard :user-id="store.player.id" />
        </div>
        <div v-loading="loading" data-record-item="pluck">
            <PLuckCard :records="pluckRecords" />
        </div>
    </MasonryLayout>
</template>

<script lang="ts" setup>
import { ElMessage, vLoading } from 'element-plus';
import { nextTick, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import PathCard from './PathCard.vue';
import PLuckCard from './PLuckCard.vue';
import SaoleiCard from './SaoleiCard.vue';
import StrictNgCard from './StrictNgCard.vue';

import MasonryLayout from '@/components/common/MasonryLayout.vue';
import type { CustomPluckRecord } from '@/services/msuserService';
import { fetchCustomPluckPlayerRecords } from '@/services/msuserService';
import { store } from '@/store';

const i18nMessages = {
    'zh-cn': { local: {
        loadFailed: '自定义密度纪录加载失败',
    } },
    en: { local: {
        loadFailed: 'Could not load custom density records',
    } },
    es: { local: {
        loadFailed: 'No se pudieron cargar los récords de densidad personalizada',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const loading = ref(true);
const pluckRecords = ref<CustomPluckRecord[]>([]);

// 此处和父组件配合，等一下从store里获取用户的id
void nextTick(() => {
    const playerId = store.player.id;
    void fetchCustomPluckPlayerRecords(playerId).then((data) => {
        pluckRecords.value = data;
    }).catch(() => {
        ElMessage.error({ message: t('local.loadFailed'), offset: 68 });
    }).finally(() => {
        loading.value = false;
    });
});
</script>

<style scoped>
.user-record-view {
    --ui-table-cell-padding-block: 4px;
    --ui-table-cell-padding-inline: 6px;
}
</style>
