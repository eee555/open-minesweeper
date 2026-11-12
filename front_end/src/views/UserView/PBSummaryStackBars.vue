<template>
    <section class="pb-stackbars" data-cy="pb-stackbars">
        <div v-for="bar in bars" :key="bar.key" class="pb-stackbar-row" :data-cy="`pb-stackbar-${bar.key}`">
            <span class="pb-stackbar-label text-secondary">{{ bar.label }}</span>
            <span class="pb-stackbar-value text-regular" :title="bar.title">{{ formatDerivedValue(bar.metric, bar.value) }}({{ formatRank(bar.rank) }})</span>
            <div class="pb-stackbar-chart">
                <StackBar :data="bar.items" :format-value="(value) => formatDerivedValue(bar.metric, value)" height="10px" legend />
            </div>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import StackBar from '@/components/visualization/StackBar/App.vue';
import type { DerivedDisplayMetric, DerivedRankingName, DerivedRanksMap, DerivedRecordsMap } from '@/services/pbDerivedService';
import { derivedLevels, derivedTitle, formatDerivedValue, formatRank, modeKey } from '@/services/pbDerivedService';
import { colorTheme } from '@/store';

interface StackBarItem {
    name: string;
    value: number;
    color: string;
}

interface BarDefinition {
    key: string;
    labelKey: string;
    ranking: DerivedRankingName;
    suffix: string;
    metric: DerivedDisplayMetric;
}

const props = defineProps({
    records: { type: Object as PropType<DerivedRecordsMap>, required: true },
    ranks: { type: Object as PropType<DerivedRanksMap>, required: true },
    nf: { type: Boolean, default: false },
});

const definitions: BarDefinition[] = [
    { key: 'count', labelKey: 'derived.count', ranking: 'collection', suffix: 'count', metric: 'count' },
    { key: 'probability', labelKey: 'derived.probability', ranking: 'collection', suffix: 'probability', metric: 'probability' },
    { key: 'asb', labelKey: 'derived.asb', ranking: 'collection', suffix: 'asb', metric: 'asb' },
    { key: 'skill', labelKey: 'derived.skill', ranking: 'skill', suffix: 'total', metric: 'skill' },
    { key: 'tt', labelKey: 'derived.typicalTime', ranking: 'typical_time', suffix: 'total', metric: 'tt' },
];

const bars = computed(() => {
    const mode = modeKey(props.nf);
    return definitions.map((definition) => {
        const { ranking, suffix, metric } = definition;
        const totalField = `${mode}:sum:${suffix}`;
        const value = props.records[ranking]?.[totalField];
        const rank = props.ranks[ranking]?.[totalField];
        const items: StackBarItem[] = derivedLevels.map((level) => ({
            name: t(`level.${level}`),
            value: props.records[ranking]?.[`${mode}:${level}:${suffix}`] ?? 0,
            color: colorTheme.value.level[level],
        }));
        return {
            key: definition.key,
            label: t(definition.labelKey),
            metric,
            value,
            rank,
            title: derivedTitle(metric, value),
            items,
        };
    });
});

const { t } = useI18n();
</script>

<style scoped>
.pb-stackbars {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}
.pb-stackbar-row {
    display: grid;
    grid-template-columns: minmax(6em, auto) minmax(8em, auto) minmax(0, 1fr);
    align-items: center;
    gap: 8px;
}
.pb-stackbar-label {
    white-space: nowrap;
}
.pb-stackbar-value {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}
.pb-stackbar-chart {
    min-width: 0;
}
</style>
