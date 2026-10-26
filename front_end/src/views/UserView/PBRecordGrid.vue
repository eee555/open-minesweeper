<template>
    <section class="pb-records" :data-cy="`pb-grid-${level}`">
        <h3 class="text-regular">
            {{ t(`common.level.${level}`) }}
        </h3>
        <p v-if="recordsByBV.size === 0" class="text-info" data-cy="pb-empty">
            {{ t('local.empty') }}
        </p>
        <div v-else class="pb-grid-scroll">
            <div class="pb-grid">
                <span />
                <span v-for="digit in 10" :key="`head-${digit}`" class="pb-label">{{ digit - 1 }}</span>
                <template v-for="row in rows" :key="row.start">
                    <span class="pb-label">{{ row.start }}–{{ row.start + 9 }}</span>
                    <template v-for="cell in row.cells" :key="cell.bv">
                        <span v-if="cell.record" :title="recordTitle(cell.record)" :style="cellStyle(cell.record)" class="pb-cell" :data-cy="`pb-${level}-${cell.bv}`">
                            <VideoPreviewLink :id="cell.record.video_id">
                                {{ value(cell.record) }}
                            </VideoPreviewLink>
                        </span>
                        <span v-else class="pb-cell" />
                    </template>
                </template>
            </div>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import type { PBPlayerRecord, PBStat } from '@/services/pbRankingService';
import { formatPBValue, pbStats } from '@/services/pbRankingService';
import { colorThemes } from '@/store/color';
import { ArrayUtils } from '@/utils/arrays';
import { PiecewiseColorScheme } from '@/utils/colors';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';
import type { MS_Level } from '@/utils/ms_const';

const props = defineProps({
    records: { type: Array<PBPlayerRecord>, required: true },
    level: { type: String as PropType<MS_Level>, required: true },
    nf: { type: Boolean, default: false },
    stat: { type: String as PropType<PBStat | 'rank'>, default: 'time' },
});
const rankTheme = new PiecewiseColorScheme([
    '#FFC000', '#A0A0A0', '#CD7F32',
    'rgba(64, 158, 255, 0.22)', 'rgba(64, 158, 255, 0.14)', 'rgba(64, 158, 255, 0.07)', 'transparent',
], [1, 2, 3, 10, 50, 100]);
const recordsByBV = computed(() => new Map(props.records.filter((record) => record.level === props.level && record.nf === props.nf).map((record) => [record.bv, record])));
const rows = computed(() => {
    if (!recordsByBV.value.size) return [];
    const bvs = [...recordsByBV.value.keys()];
    return ArrayUtils.range(Math.floor(Math.min(...bvs) / 10) * 10, Math.floor(Math.max(...bvs) / 10) * 10, 10).
        map((start) => ({ start, cells: ArrayUtils.range(start, start + 9).map((bv) => ({ bv, record: recordsByBV.value.get(bv) })) }));
});
function value(record: PBPlayerRecord) {
    return props.stat === 'rank' ? String(record.rank ?? '--') : formatPBValue(record.timems, props.level, record.bv, props.stat);
}
function recordTitle(record: PBPlayerRecord): string {
    return [
        `BV ${record.bv}${record.nf ? ' · NF' : ''}`,
        ...pbStats.map((metric) => `${t(`common.prop.${metric}`)}: ${formatPBValue(record.timems, record.level, record.bv, metric)}`),
        `${t('common.prop.rank')}: ${record.rank ?? '--'}`,
    ].join('\n');
}
function cellStyle(record: PBPlayerRecord) {
    if (props.stat === 'rank') {
        const medal = record.rank !== null && record.rank >= 1 && record.rank <= 3;
        return { backgroundColor: rankTheme.getColor(record.rank ?? NaN), color: medal ? '#141414' : 'var(--ui-text-color-regular)' };
    }
    const theme = colorThemes[getPiecewiseColorSchemeName(props.stat, props.level)].value;
    const numericValue = props.stat === 'time' ? record.timems / 1000 : Number(formatPBValue(record.timems, props.level, record.bv, props.stat));
    return theme.getStyle(numericValue);
}
const i18nMessages = {
    'zh-cn': { local: {
        empty: '暂无 PB 纪录',
    } },
    en: { local: {
        empty: 'No PB records',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.pb-records h3 {
    margin: 0 0 0.35rem;
}
.pb-grid-scroll {
    overflow-x: auto;
}
.pb-grid {
    display: grid;
    grid-template-columns: 4.5em repeat(10, minmax(4.3em, 1fr));
    min-width: 50em;
    grid-auto-rows: 25px;
}
.pb-label, .pb-cell {
    display: flex;
    align-items: center;
    justify-content: center;
}
.pb-label {
    color: var(--ui-text-color-secondary);
}
.pb-cell {
    outline: 1px solid var(--ui-border-color-lighter);
}
</style>
