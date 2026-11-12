<template>
    <section class="pb-records" :data-cy="`pb-grid-${level}`">
        <h3 class="pb-level-title text-regular">
            {{ t(`level.${level}`) }}
            <span v-for="item in levelSummary" :key="item.key" class="pb-level-stat text-secondary" :title="item.title">{{ item.label }} {{ item.text }}</span>
        </h3>
        <p v-if="recordsByBV.size === 0" class="text-info" data-cy="pb-empty">
            {{ t('local.empty') }}
        </p>
        <div v-else class="pb-grid-scroll">
            <div class="pb-grid-layout">
                <div class="pb-grid">
                    <span />
                    <span v-for="digit in 10" :key="`head-${digit}`" class="pb-label text-secondary">{{ digit - 1 }}</span>
                    <template v-for="row in rows" :key="row.start">
                        <span class="pb-label text-secondary">{{ row.start }}–{{ row.start + 9 }}</span>
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
                <div v-if="sideColumns.length" class="pb-side-grid" :style="sideGridStyle">
                    <span v-for="(column, index) in sideColumns" :key="column.key" class="pb-label pb-side-head text-secondary" :style="{ gridRow: 1, gridColumn: index + 1 }">
                        {{ column.label }}
                    </span>
                    <span v-for="cell in sideCells" :key="cell.key" class="pb-cell pb-side-cell" :title="cell.title" :style="sideCellStyle(cell)" :data-cy="cell.key">
                        {{ cell.text }}
                    </span>
                </div>
            </div>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { CSSProperties, PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import type { DerivedRankingName, DerivedRanksMap, DerivedRecordsMap } from '@/services/pbDerivedService';
import { derivedSegments, derivedTitle, formatDerivedNumber, formatDerivedValue, formatRank, modeKey } from '@/services/pbDerivedService';
import type { PBPlayerRecord, PBStat } from '@/services/pbRankingService';
import { formatPBValue, pbStats } from '@/services/pbRankingService';
import { colorThemes } from '@/store/color';
import { ArrayUtils } from '@/utils/arrays';
import { PiecewiseColorScheme } from '@/utils/colors';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';
import type { MS_Level } from '@/utils/ms_const';

interface SideColumn {
    key: string;
    label: string;
    ranking: DerivedRankingName;
    kind: 'skill' | 'tt' | 'rank';
}

interface SideCell {
    key: string;
    text: string;
    title: string;
    kind: 'skill' | 'tt' | 'rank';
    value: number | undefined;
    rank: number | null | undefined;
    gridRow: string;
    gridColumn: number;
}

const props = defineProps({
    records: { type: Array<PBPlayerRecord>, required: true },
    level: { type: String as PropType<MS_Level>, required: true },
    nf: { type: Boolean, default: false },
    stat: { type: String as PropType<PBStat | 'rank'>, default: 'time' },
    derivedRecords: { type: Object as PropType<DerivedRecordsMap>, required: true },
    derivedRanks: { type: Object as PropType<DerivedRanksMap>, required: true },
    colored: { type: Boolean, default: false },
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

const levelSummaryItems = [
    { key: 'count', labelKey: 'derived.count', ranking: 'collection', suffix: 'count', metric: 'count' },
    { key: 'probability', labelKey: 'derived.probability', ranking: 'collection', suffix: 'probability', metric: 'probability' },
    { key: 'asb', labelKey: 'derived.asb', ranking: 'collection', suffix: 'asb', metric: 'asb' },
    { key: 'skill', labelKey: 'derived.skill', ranking: 'skill', suffix: 'total', metric: 'skill' },
    { key: 'tt', labelKey: 'derived.typicalTime', ranking: 'typical_time', suffix: 'total', metric: 'tt' },
] as const;

const levelSummary = computed(() => {
    const mode = modeKey(props.nf);
    return levelSummaryItems.map((item) => {
        const field = `${mode}:${props.level}:${item.suffix}`;
        const fieldValue = props.derivedRecords[item.ranking]?.[field];
        const rank = props.derivedRanks[item.ranking]?.[field];
        return {
            key: item.key,
            label: t(item.labelKey),
            text: `${formatDerivedValue(item.metric, fieldValue)}(${formatRank(rank)})`,
            title: derivedTitle(item.metric, fieldValue),
        };
    });
});

const sideColumns = computed<SideColumn[]>(() => {
    if (props.stat === 'time') return [{ key: 'tt', label: t('derived.typicalTime'), ranking: 'typical_time', kind: 'tt' }];
    if (props.stat === 'bvs') return [{ key: 'skill', label: t('derived.skill'), ranking: 'skill', kind: 'skill' }];
    if (props.stat === 'rank') return [
        { key: 'skill-rank', label: t('derived.skillRank'), ranking: 'skill', kind: 'rank' },
        { key: 'tt-rank', label: t('derived.ttRank'), ranking: 'typical_time', kind: 'rank' },
    ];
    return [];
});

const sideGridStyle = computed<CSSProperties>(() => ({
    gridTemplateColumns: `repeat(${sideColumns.value.length}, minmax(5em, 1fr))`,
    minWidth: `${5 * sideColumns.value.length}em`,
}));

const sideCells = computed<SideCell[]>(() => {
    if (!rows.value.length || !sideColumns.value.length) return [];
    const mode = modeKey(props.nf);
    const firstRow = Math.floor(rows.value[0].start / 10);
    const lastRow = Math.floor(rows.value[rows.value.length - 1].start / 10);
    const cells: SideCell[] = [];
    for (const segment of derivedSegments[props.level]) {
        const from = Math.max(Math.floor(segment.start / 10), firstRow);
        const to = Math.min(Math.floor(segment.end / 10), lastRow);
        if (from > to) continue;
        for (const [index, column] of sideColumns.value.entries()) {
            const field = `${mode}:${props.level}:${segment.field}`;
            const fieldValue = props.derivedRecords[column.ranking]?.[field];
            const rank = props.derivedRanks[column.ranking]?.[field];
            const text = column.kind === 'rank' ? formatRank(rank) : formatDerivedNumber(fieldValue);
            cells.push({
                key: `pb-side-${props.level}-${segment.field}-${column.key}`,
                text,
                title: column.kind === 'rank' ? `${segment.start}–${segment.end}` : derivedTitle(column.kind, fieldValue),
                kind: column.kind,
                value: fieldValue,
                rank,
                gridRow: `${from - firstRow + 2} / span ${to - from + 1}`,
                gridColumn: index + 1,
            });
        }
    }
    return cells;
});

function sideCellStyle(cell: SideCell): CSSProperties {
    const style: CSSProperties = { gridRow: cell.gridRow, gridColumn: cell.gridColumn };
    if (!props.colored) return style;
    if (cell.kind === 'skill' && cell.value !== undefined) return { ...style, ...colorThemes.bvs.value.getStyle(cell.value) };
    if (cell.kind === 'tt' && cell.value !== undefined) {
        return { ...style, ...colorThemes[getPiecewiseColorSchemeName('time', props.level)].value.getStyle(cell.value) };
    }
    if (cell.kind === 'rank') {
        const medal = cell.rank !== null && cell.rank !== undefined && cell.rank >= 1 && cell.rank <= 3;
        return { ...style, backgroundColor: rankTheme.getColor(cell.rank ?? NaN), color: medal ? '#141414' : 'var(--ui-text-color-regular)' };
    }
    return style;
}

function value(record: PBPlayerRecord) {
    return props.stat === 'rank' ? String(record.rank ?? '--') : formatPBValue(record.timems, props.level, record.bv, props.stat);
}
function recordTitle(record: PBPlayerRecord): string {
    return [
        `BV ${record.bv}${record.nf ? ' · NF' : ''}`,
        ...pbStats.map((metric) => `${t(`prop.${metric}`)}: ${formatPBValue(record.timems, record.level, record.bv, metric)}`),
        `${t('prop.rank')}: ${record.rank ?? '--'}`,
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
.pb-level-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0 0.75rem;
}
.pb-level-stat {
    font-size: 0.85em;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}
.pb-grid-scroll {
    overflow-x: auto;
}
.pb-grid-layout {
    display: flex;
    align-items: flex-start;
    width: max-content;
    min-width: 100%;
}
.pb-grid {
    display: grid;
    grid-template-columns: 4.5em repeat(10, minmax(4.3em, 1fr));
    min-width: 50em;
    grid-auto-rows: 25px;
    flex: 0 0 auto;
}
.pb-side-grid {
    display: grid;
    grid-auto-rows: 25px;
    flex: 0 0 auto;
}
.pb-label, .pb-cell {
    display: flex;
    align-items: center;
    justify-content: center;
}
.pb-cell {
    outline: 1px solid var(--ui-border-color-lighter);
}
.pb-side-cell {
    text-align: center;
    font-variant-numeric: tabular-nums;
}
.pb-side-head {
    font-size: 0.8em;
    text-align: center;
    white-space: nowrap;
}
</style>
