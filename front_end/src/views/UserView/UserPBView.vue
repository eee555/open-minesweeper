<template>
    <section class="pb-summary" :aria-busy="loading" data-cy="pb-summary">
        <div class="pb-controls">
            <label class="checkbox checkbox--small"><input v-model="nf" class="checkbox-input" type="checkbox"> NF</label>
            <div class="button-group button-group--joined" role="group" :aria-label="t('common.prop.metric')" data-cy="pb-stat">
                <BaseButton v-for="metric in summaryStats" :key="metric" size="small" :type="stat === metric ? 'primary' : 'default'" :aria-pressed="stat === metric" :data-stat="metric" @click="stat = metric">
                    {{ metric === 'rank' ? t('common.prop.rank') : t(`common.prop.${metric}`) }}
                </BaseButton>
            </div>
            <BaseButton size="small" :loading="loading" data-cy="refresh-pb" @click="load(true)">
                {{ t('common.action.refresh') }}
            </BaseButton>
        </div>
        <p v-if="loading" role="status">
            {{ t('local.loading') }}
        </p>
        <p v-else-if="failed" role="alert">
            {{ t('local.failed') }}
        </p>
        <template v-else-if="loadedKey === dataKey">
            <PBRecordGrid v-for="level in pbLevels" :key="level" :records="records" :level="level" :nf="nf" :stat="stat" />
        </template>
    </section>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import '@/styles/checkbox.css';
import { computed, onActivated, onDeactivated, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import PBRecordGrid from './PBRecordGrid.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import type { PBPlayerRecord, PBStat } from '@/services/pbRankingService';
import { fetchPBPlayerRecords, pbLevels, pbStats } from '@/services/pbRankingService';
import { profileDataRevision } from '@/services/profileDataService';
import { store } from '@/store';
import { UserProfile } from '@/utils/userprofile';

const user = defineModel('user', { type: UserProfile, required: true });
const route = useRoute();
const activated = ref(true);
onActivated(() => {
    activated.value = true;
});
onDeactivated(() => {
    activated.value = false;
});
const active = computed(() => activated.value && route.name === 'user-pb' && Number(route.params.id) === user.value.id);
const dataKey = computed(() => `${user.value.id}:${store.sessionRevision}:${profileDataRevision(user.value.id)}`);
const loadedKey = ref('');
const records = ref<PBPlayerRecord[]>([]);
const summaryStats = [...pbStats, 'rank'] as const;
const stat = ref<PBStat | 'rank'>('time');
const nf = ref(false);
const loading = ref(false);
const failed = ref(false);
let requestNumber = 0;
async function load(force = false) {
    const number = ++requestNumber;
    loading.value = false;
    if (!active.value || user.value.id < 1) return;
    if (!force && loadedKey.value === dataKey.value) return;
    const key = dataKey.value;
    loading.value = true;
    failed.value = false;
    try {
        const result = await fetchPBPlayerRecords(user.value.id);
        if (dataKey.value !== key || number !== requestNumber) return;
        records.value = result;
        loadedKey.value = key;
    } catch {
        if (number === requestNumber) failed.value = true;
    } finally {
        if (number === requestNumber) loading.value = false;
    }
}
watch([active, dataKey], () => {
    void load();
}, { immediate: true });
const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在加载 PB 纪录…',
        failed: 'PB 纪录加载失败，请点击刷新重试。',
    } },
    en: { local: {
        loading: 'Loading PB records…',
        failed: 'Could not load PB records. Refresh to retry.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.pb-summary {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.pb-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.pb-controls label {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}
</style>
