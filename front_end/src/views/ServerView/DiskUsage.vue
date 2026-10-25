<template>
    <RefreshableCard data-statistic="disk" class="statistics-card" :title="t('local.title')" :loading="loading" @refresh="emit('refresh')">
        <p v-if="failed || invalid" role="alert" class="text-danger">
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
                {{ t('statistics.total') }}: {{ formatBytes(total) }}
            </div>
        </template>
        <p v-else-if="!loading && !failed && !invalid" role="status">
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
import { computed, ref, shallowRef, watch } from 'vue';
import type { VueUiDonutConfig } from 'vue-data-ui';
import { VueUiDonut } from 'vue-data-ui';
import { useI18n } from 'vue-i18n';

import { statisticsColors } from './statistics';
import type { DiskUsage } from './statistics';

import RefreshableCard from '@/components/common/RefreshableCard.vue';
import { local } from '@/store';
import { formatBytes } from '@/utils/strings';

const props = defineProps({
    section: { type: Object as PropType<DiskUsage | null>, default: null },
    loading: { type: Boolean, default: false },
    failed: { type: Boolean, default: false },
});
const emit = defineEmits<{ refresh: [] }>();
const data = shallowRef<DiskUsage | null>(null);
const invalid = ref(false);
watch(() => props.section, (disk) => {
    invalid.value = false;
    if (!disk) return;
    const values = [disk.total, disk.free, disk.video ?? 0, disk.db ?? 0];
    if (values.some((value) => !Number.isFinite(value) || value < 0) || disk.free + (disk.video ?? 0) + (disk.db ?? 0) > disk.total) {
        invalid.value = true;
        return;
    }
    data.value = disk;
}, { immediate: true });
const total = computed(() => data.value?.total ?? null);
const dataset = computed(() => {
    if (data.value === null) return [];
    const { total: diskTotal, free, video, db } = data.value;
    return [
        { key: 'video', name: t('local.video'), values: [video ?? 0], color: statisticsColors[0] },
        { key: 'db', name: t('local.db'), values: [db ?? 0], color: statisticsColors[1] },
        { key: 'other', name: t('local.other'), values: [diskTotal - free - (video ?? 0) - (db ?? 0)], color: statisticsColors[5] },
        { key: 'free', name: t('local.free'), values: [free], color: statisticsColors[2] },
    ];
});

const config = computed<VueUiDonutConfig>(() => ({
    theme: local.value.darkmode ? 'dark' : '',
    useCssAnimation: false,
    userOptions: { show: false },
    style: { chart: {
        backgroundColor: 'transparent',
        legend: { show: true, showValue: true, showPercentage: true, roundingPercentage: 1, fontSize: 12, backgroundColor: 'transparent' },
        tooltip: { show: false },
        layout: { labels: {
            value: { formatter: ({ value }) => formatBytes(value) },
            hollow: {
                average: { show: false },
                total: { text: t('statistics.total'), value: { formatter: ({ value }) => formatBytes(value) } },
            },
        } },
    } },
}));

const i18nMessages = {
    'zh-cn': { local: {
        cache: '每 5 分钟定时采样，刷新读取最近一次结果。',
        title: '磁盘使用情况',
        video: '录像文件',
        db: '数据库',
        other: '其他文件',
        free: '可用空间',
    } },
    en: { local: {
        cache: 'Sampled every 5 minutes. Refresh loads the latest sample.',
        title: 'Disk Usage',
        video: 'Videos',
        db: 'Database',
        other: 'Other',
        free: 'Free',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
</script>
