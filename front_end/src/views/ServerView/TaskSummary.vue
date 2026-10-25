<template>
    <RefreshableCard data-statistic="tasks" class="statistics-card" :title="t('local.title')" :loading="loading" @refresh="emit('refresh')">
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('statistics.requestFailed') }}
            <span v-if="total !== null">{{ t('statistics.previous') }}</span>
        </p>
        <p v-if="loading && total === null" role="status">
            {{ t('statistics.loading') }}
        </p>
        <template v-if="total !== null">
            <VueUiDonut v-if="total > 0" :dataset="dataset" :config="config" />
            <p v-else role="status">
                {{ t('statistics.empty') }}
            </p>
            <div class="statistics-total">
                {{ t('statistics.total') }}: {{ formatCount(total) }}
            </div>
        </template>
        <p v-else-if="!loading && !failed" role="status">
            {{ t('statistics.unavailable') }}
        </p>
        <div v-if="data?.sampled_at" class="statistics-time">
            {{ t('statistics.sampled') }}: <time :datetime="data.sampled_at">{{ new Date(data.sampled_at).toLocaleString(locale) }}</time>
        </div>
        <p class="statistics-cache-note">
            {{ t('local.cache') }}
        </p>
    </RefreshableCard>
</template>

<script setup lang="ts">
import 'vue-data-ui/style.css';
import './statistics.css';
import type { PropType } from 'vue';
import { computed } from 'vue';
import type { VueUiDonutConfig } from 'vue-data-ui';
import { VueUiDonut } from 'vue-data-ui';
import { useI18n } from 'vue-i18n';

import { statisticsColors } from './statistics';
import type { TaskSummary } from './statistics';

import RefreshableCard from '@/components/common/RefreshableCard.vue';
import { local } from '@/store';

const props = defineProps({
    section: { type: Object as PropType<TaskSummary | null>, default: null },
    loading: { type: Boolean, default: false },
    failed: { type: Boolean, default: false },
});
const emit = defineEmits<{ refresh: [] }>();
const statuses = ['READY', 'RUNNING', 'SUCCESSFUL', 'FAILED'] as const;
const data = computed(() => props.section);
const total = computed(() => data.value?.total ?? null);
const dataset = computed(() => (data.value === null
    ? []
    : statuses.map((key, index) => ({
        key, name: t(`local.${key}`), values: [data.value?.status[key] ?? 0], color: statisticsColors[index],
    }))));

function formatCount(value: number) {
    return new Intl.NumberFormat(locale.value).format(value);
}

const config = computed<VueUiDonutConfig>(() => ({
    theme: local.value.darkmode ? 'dark' : '',
    useCssAnimation: false,
    userOptions: { show: false },
    style: { chart: {
        backgroundColor: 'transparent',
        legend: { show: true, showValue: true, showPercentage: true, roundingPercentage: 1, fontSize: 12, backgroundColor: 'transparent' },
        tooltip: { show: false },
        layout: { labels: {
            value: { formatter: ({ value }) => formatCount(value) },
            hollow: {
                average: { show: false },
                total: { text: t('statistics.total'), value: { formatter: ({ value }) => formatCount(value) } },
            },
        } },
    } },
}));

const i18nMessages = {
    'zh-cn': { local: {
        cache: '每 5 分钟定时采样，刷新读取最近一次结果。',
        title: '后台任务',
        READY: '排队中',
        RUNNING: '运行中',
        SUCCESSFUL: '已完成',
        FAILED: '失败',
    } },
    en: { local: {
        cache: 'Sampled every 5 minutes. Refresh loads the latest sample.',
        title: 'Background tasks',
        READY: 'Ready',
        RUNNING: 'Running',
        SUCCESSFUL: 'Successful',
        FAILED: 'Failed',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
</script>
