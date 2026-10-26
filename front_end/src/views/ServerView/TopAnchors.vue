<template>
    <BaseCardNormal data-statistic="top-anchors" class="statistics-card">
        <h2 class="anchor-title">
            {{ t('local.title') }}
        </h2>
        <p v-if="loading && !data" role="status">
            {{ t('statistics.loading') }}
        </p>
        <template v-if="data">
            <section v-for="stat in topStats" :key="stat" class="anchor-panel" :data-stat="stat">
                <h3>{{ t(`common.prop.${topStatNames[stat]}`) }}</h3>
                <VueUiXy :dataset="datasets[stat]" :config="chartConfig" />
            </section>
            <BaseTable class="anchor-values" :column-count="4">
                <template #head>
                    <tr>
                        <th scope="col">
                            {{ t('common.prop.level') }}
                        </th><th scope="col">
                            {{ t('common.prop.metric') }}
                        </th><th scope="col">
                            top
                        </th><th scope="col">
                            NF top
                        </th>
                    </tr>
                </template>
                <tr v-for="axis in topAxes" :key="`${axis.level}${axis.stat}`">
                    <th scope="row">
                        {{ t(`common.level.${axis.level}`) }}
                    </th>
                    <td>{{ t(`common.prop.${topStatNames[axis.stat]}`) }}</td>
                    <td v-for="nf in [false, true]" :key="String(nf)" class="table-col-number" :data-anchor="topField(nf, axis.level, axis.stat)" :title="t('local.samples', { count: data[topField(nf, axis.level, axis.stat)]?.sample_count ?? 0 })">
                        {{ formatTopValue(data[topField(nf, axis.level, axis.stat)]?.value ?? 0, axis.level, axis.stat) }}
                    </td>
                </tr>
            </BaseTable>
        </template>
        <p v-else-if="!loading" role="status">
            {{ t('statistics.unavailable') }}
        </p>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import 'vue-data-ui/style.css';
import './statistics.css';
import { computed } from 'vue';
import { VueUiXy } from 'vue-data-ui';
import type { VueUiXyConfig, VueUiXyDatasetItem } from 'vue-data-ui';
import { useI18n } from 'vue-i18n';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { formatTopValue, topAxes, topDisplayValue, topField, topLevels, topStatNames, topStats } from '@/services/topRankingService';
import type { TopStat } from '@/services/topRankingService';
import { local, store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';

const data = computed(() => store.topAnchors);
const loading = computed(() => store.login_status === LoginStatus.Undefined);
function dataset(stat: TopStat): VueUiXyDatasetItem[] {
    return [false, true].map((nf) => ({
        name: nf ? 'NF top' : 'top',
        type: 'bar',
        color: nf ? '#E6A23C' : '#409EFF',
        series: topLevels.map((level) => topDisplayValue(data.value?.[topField(nf, level, stat)]?.value ?? 0, level, stat)),
    }));
}
const datasets = computed(() => ({ t: dataset('t'), b: dataset('b'), s: dataset('s') }));
const chartConfig = computed<VueUiXyConfig>(() => ({
    theme: local.value.darkmode ? 'dark' : '',
    useCssAnimation: false,
    chart: {
        backgroundColor: 'transparent',
        height: 230,
        grid: { labels: { xAxisLabels: { values: topLevels.map((level) => t(`common.level.${level}`)) }, yAxis: { rounding: 3 } } },
        legend: { show: true, fontSize: 12 },
        userOptions: { show: false },
        zoom: { show: false },
        tooltip: { roundingValue: 3, showPercentage: false },
    },
    bar: { useGradient: false, borderRadius: 0, labels: { show: true, rounding: 3 } },
}));

const i18nMessages = {
    'zh-cn': { local: {
        title: 'top 锚点',
        samples: '样本人数：{count}',
    } },
    en: { local: {
        title: 'top anchors',
        samples: 'Sample size: {count}',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.anchor-title {
    margin: 0;
    font-size: var(--ui-font-size-medium);
}
.anchor-panel {
    min-width: 0;
}
.anchor-panel h3 {
    margin: 6px 0 0;
    font-size: var(--ui-font-size-base);
}
.anchor-values {
    font-size: var(--ui-font-size-small);
}
</style>
