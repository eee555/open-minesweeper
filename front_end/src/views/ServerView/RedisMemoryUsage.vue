<template>
    <RefreshableCard data-memory-chart="redis" class="statistics-card" :title="t('local.title')" :loading="loading" @refresh="emit('refresh')">
        <p v-if="failed || reason !== null" role="alert" class="text-danger">
            {{ failed ? t('statistics.requestFailed') : reason === null ? '' : t(`statistics.memoryFailure.${reason}`) }}
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
            <p v-if="lastGood" class="memory-description" :title="t('local.explanation')">
                {{ t('local.estimated') }}
            </p>
            <div v-if="lastGood?.sampled_at" class="statistics-time">
                {{ t('statistics.sampled') }}: <time :datetime="lastGood.sampled_at">{{ new Date(lastGood.sampled_at).toLocaleString(locale) }}</time>
            </div>
        </template>
        <p v-else-if="!loading && !failed && reason === null" role="status">
            {{ t('statistics.unavailable') }}
        </p>
        <p class="statistics-cache-note">
            {{ t('local.cache') }}
        </p>
    </RefreshableCard>
</template>

<script setup lang="ts">
import 'vue-data-ui/style.css';
import './statistics.css';
import type { PropType } from 'vue';
import { computed, shallowRef, watch } from 'vue';
import type { VueUiDonutConfig } from 'vue-data-ui';
import { VueUiDonut } from 'vue-data-ui';
import { useI18n } from 'vue-i18n';

import type { RedisMemorySection } from './memory';
import { memoryColors, redisMemoryGroups } from './memory';

import RefreshableCard from '@/components/common/RefreshableCard.vue';
import { local } from '@/store';
import { formatBytes } from '@/utils/strings';

const props = defineProps({
    section: { type: Object as PropType<RedisMemorySection | null>, default: null },
    loading: { type: Boolean, default: false },
    failed: { type: Boolean, default: false },
});
const emit = defineEmits<{ refresh: [] }>();
const reason = computed(() => props.section?.reason ?? null);
const lastGood = shallowRef<RedisMemorySection | null>(null);
watch(() => props.section, (section) => {
    if (section?.status === 'ready' && section.groups && section.total_bytes !== null && section.sampled_at !== null && section.sampled_at.length > 0) lastGood.value = section;
}, { immediate: true });
const total = computed(() => lastGood.value?.total_bytes ?? null);
const dataset = computed(() => {
    const groups = lastGood.value?.groups;
    return groups ? redisMemoryGroups.map((key, index) => ({ key, name: t(`local.${key}`), values: [groups[key]], color: memoryColors[index] })) : [];
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
        title: 'Redis 内存分布',
        pb_rankings: 'PB 榜',
        other_rankings: '其他排行榜',
        latest_videos: '最新录像',
        other: '其他',
        estimated: 'Redis 已分配内存（估算）',
        explanation: '包括其他数据库和 Redis 自身开销，与进程驻留内存的统计口径不同。',
    } },
    en: { local: {
        cache: 'Sampled every 5 minutes. Refresh loads the latest sample.',
        title: 'Redis Memory Distribution',
        pb_rankings: 'PB rankings',
        other_rankings: 'Other rankings',
        latest_videos: 'Latest videos',
        other: 'Other',
        estimated: 'Allocated Redis memory (estimated)',
        explanation: 'Includes other databases and Redis overhead. This differs from resident process memory.',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.memory-description {
    margin: 4px 0;
    font-size: var(--ui-font-size-small);
    overflow-wrap: anywhere;
}
</style>
