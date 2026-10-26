<template>
    <section class="top-summary" data-cy="top-summary" :aria-busy="loading">
        <div v-if="softValues" class="top-lsf-heading">
            LSF <strong data-cy="lsf-value">{{ formatLsf(softValues.lsf) }}</strong>
        </div>
        <div class="top-summary-toolbar">
            <div class="top-lsf-summary" data-cy="top-lsf-summary">
                <StackBar v-if="softValues" :data="lsfContributions" height="10px" :format-value="formatLsf" legend />
            </div>
            <BaseButton class="square-button top-summary-refresh" size="small" :disabled="loading" :aria-busy="loading || undefined" :aria-label="t('action.refresh')" :title="t('action.refresh')" data-cy="refresh-top" @click="loadRecords(true)">
                <BaseIconRefresh :loading="loading" aria-hidden="true" />
            </BaseButton>
        </div>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('local.recordsFailed') }}
        </p>
        <p v-if="loading && !visibleRecords" role="status">
            {{ t('local.loading') }}
        </p>
        <div v-if="visibleRecords" class="top-radars">
            <section v-for="nf in [false, true]" :key="String(nf)" class="top-panel">
                <TopRadar v-if="anchors" :records="visibleRecords" :anchors="anchors" :nf="nf" />
                <h3 v-else>
                    {{ nf ? 'NF top' : 'top' }}
                </h3>
                <TopRecordTable :records="visibleRecords" :nf="nf" />
            </section>
        </div>
    </section>
</template>

<script setup lang="ts">
import tinycolor from 'tinycolor2';
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import TopRadar from './TopRadar.vue';
import TopRecordTable from './TopRecordTable.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import StackBar from '@/components/visualization/StackBar/App.vue';
import { fetchTopPlayerRecords, topLsfContributions, topSoftValues } from '@/services/topRankingService';
import type { TopRecords } from '@/services/topRankingService';
import { colorTheme, store } from '@/store';

const props = defineProps({
    userId: { type: Number, required: true },
    active: { type: Boolean, default: true },
    revision: { type: String, default: '' },
});
const dataKey = computed(() => `${props.userId}:${props.revision}`);
const loadedKey = ref('');
const records = shallowRef<TopRecords | null>(null);
const anchors = computed(() => store.topAnchors);
const visibleRecords = computed(() => (props.active && loadedKey.value === dataKey.value ? records.value : null));
const softValues = computed(() => (visibleRecords.value && anchors.value ? topSoftValues(visibleRecords.value, anchors.value) : null));
const lsfContributions = computed(() => (softValues.value
    ? topLsfContributions(softValues.value).map(({ mode, level, value }) => ({
        name: `${mode === 'nf' ? 'NF ' : ''}${t(`level.${level}`)}`,
        value,
        color: mode === 'nf' ? tinycolor(colorTheme.value.level[level]).setAlpha(0.5).toRgbString() : colorTheme.value.level[level],
    }))
    : []));
const formatLsf = (value: number) => value.toFixed(2);
const loading = ref(false);
const failed = ref(false);
let controller: AbortController | null = null;
let requestId = 0;

async function loadRecords(force = false) {
    controller?.abort();
    const request = ++requestId;
    loading.value = false;
    if (!props.active || props.userId < 1 || (!force && loadedKey.value === dataKey.value)) return;
    controller = new AbortController();
    const { signal } = controller;
    const key = dataKey.value;
    loading.value = true;
    failed.value = false;
    try {
        const result = await fetchTopPlayerRecords(props.userId, signal);
        if (request !== requestId || key !== dataKey.value) return;
        records.value = result;
        loadedKey.value = key;
    } catch {
        if (request === requestId && !signal.aborted) failed.value = true;
    } finally {
        if (request === requestId) loading.value = false;
    }
}

watch([dataKey, () => props.active], () => {
    void loadRecords();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
    controller?.abort();
});

const i18nMessages = {
    'zh-cn': { local: {
        recordsFailed: 'top 成绩加载失败，请刷新重试。',
        loading: '正在加载 top…',
    } },
    en: { local: {
        recordsFailed: 'Could not load top records. Refresh to retry.',
        loading: 'Loading top…',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.top-summary {
    min-width: 0;
    min-height: 28px;
    margin-bottom: 16px;
}
.top-summary-refresh {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
}
.top-summary-toolbar {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 12px;
}
.top-lsf-summary {
    flex: 1;
    min-width: 0;
    padding-top: 9px;
}
.top-lsf-heading {
    min-height: 28px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-variant-numeric: tabular-nums;
}
.top-radars {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
    gap: 12px;
}
.top-panel {
    min-width: 0;
}
.top-panel h3 {
    text-align: center;
    font-size: var(--ui-font-size-medium);
}
</style>
