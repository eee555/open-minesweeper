<template>
    <BaseTable v-loading="loading" class="derived-ranking-table" data-cy="derived-ranking-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="rows.length === 0 || columns.length === 0" :column-count="columns.length + 2" :empty-text="t('ranking.empty')">
        <template #head>
            <tr v-if="groups.length > 0">
                <th rowspan="2" scope="col" class="table-col-rank">
                    #
                </th>
                <th rowspan="2" scope="col" class="table-col-player">
                    {{ t('prop.player') }}
                </th>
                <th v-for="(group, index) in groups" :key="index" scope="colgroup" class="table-col-center" :colspan="group.span">
                    {{ group.label }}
                </th>
            </tr>
            <tr>
                <th v-if="groups.length === 0" scope="col" class="table-col-rank">
                    #
                </th>
                <th v-if="groups.length === 0" scope="col" class="table-col-player">
                    {{ t('prop.player') }}
                </th>
                <th v-for="column in columns" :key="column.sort" scope="col" class="table-col-number" :aria-sort="ariaSort(column)">
                    <BaseTextButton :type="sort === column.sort ? 'primary' : 'default'" :data-field="column.sort" :aria-pressed="sort === column.sort" @click="emit('selectSort', column.sort)">
                        {{ column.label }}
                    </BaseTextButton>
                </th>
            </tr>
        </template>
        <tr v-for="(row, index) in rows" :key="row.player_id">
            <td class="table-col-rank">
                {{ first + index + 1 }}
            </td>
            <td class="table-col-player">
                <PlayerName :user-id="row.player_id" />
            </td>
            <td v-for="column in columns" :key="column.sort" class="table-col-number" :data-field="column.sort" :title="valueTitle(row, column)" :style="valueStyle(row, column)" :class="{ 'derived-selected': sort === column.sort }">
                {{ formatDerivedValue(column.metric, value(row, column)) }}
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import PlayerName from '@/components/PlayerName.vue';
import { derivedTitle, formatDerivedValue } from '@/services/pbDerivedService';
import type { DerivedColumn, DerivedRankingRow } from '@/services/pbDerivedService';
import { derivedColorStyle } from '@/utils/derivedColors';

const props = defineProps({
    rows: { type: Array as PropType<DerivedRankingRow[]>, required: true },
    columns: { type: Array as PropType<DerivedColumn[]>, required: true },
    first: { type: Number, required: true },
    sort: { type: String, required: true },
    loading: { type: Boolean, required: true },
    colored: { type: Boolean, default: false },
});

const emit = defineEmits<{ selectSort: [sort: string] }>();

interface ColumnGroup {
    label: string;
    span: number;
}

const groups = computed<ColumnGroup[]>(() => {
    const result: ColumnGroup[] = [];
    for (const column of props.columns) {
        if (column.group === undefined) return [];
        const last = result[result.length - 1];
        if (last?.label === column.group) last.span++;
        else result.push({ label: column.group, span: 1 });
    }
    return result;
});

function value(row: DerivedRankingRow, column: DerivedColumn): number | undefined {
    return row.records[column.ranking]?.[column.field];
}

function valueTitle(row: DerivedRankingRow, column: DerivedColumn): string {
    return derivedTitle(column.metric, value(row, column));
}

function valueStyle(row: DerivedRankingRow, column: DerivedColumn) {
    return derivedColorStyle(column, value(row, column), props.colored);
}

function ariaSort(column: DerivedColumn): 'none' | 'ascending' | 'descending' {
    if (props.sort !== column.sort) return 'none';
    return column.ranking === 'typical_time' ? 'ascending' : 'descending';
}

const { t } = useI18n();
</script>

<style scoped>
.derived-selected {
    font-weight: 600;
}
</style>
