<template>
    <BaseTable v-loading="loading" class="pb-ranking-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="rows.length === 0" :column-count="3 + pbStats.length" :empty-text="t('ranking.empty')">
        <template #head>
            <tr>
                <th scope="col" class="table-col-rank">
                    #
                </th>
                <th scope="col" class="table-col-player">
                    {{ t('prop.player') }}
                </th>
                <th v-for="stat in pbStats" :key="stat" scope="col" class="table-col-number">
                    {{ t(`prop.${stat}`) }}
                </th>
                <th scope="col" class="table-col-datetime">
                    {{ t('prop.upload_time') }}
                </th>
            </tr>
        </template>
        <tr
            v-for="(row, index) in rows" :key="row.player_id" class="pb-ranking-row" :tabindex="loading ? -1 : 0"
            @click="previewVideo(row)" @keydown.enter.self.prevent="!loading && previewVideo(row)" @keydown.space.self.prevent="!loading && previewVideo(row)"
        >
            <td class="table-col-rank">
                {{ first + index + 1 }}
            </td>
            <td class="table-col-player">
                <PlayerName :user-id="row.player_id" />
            </td>
            <td v-for="stat in pbStats" :key="stat" class="table-col-number" :style="cellStyle(row, stat)">
                {{ formatPBValue(row.timems, level, bv, stat) }}
            </td>
            <td class="table-col-datetime">
                {{ formatPBUploadTime(row.upload_time) }}
            </td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import PlayerName from '@/components/PlayerName.vue';
import { formatPBUploadTime, formatPBValue, pbStats } from '@/services/pbRankingService';
import type { PBRankingPlayer, PBStat } from '@/services/pbRankingService';
import { colorThemes } from '@/store/color';
import { preview } from '@/utils/common/PlayerDialog';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';
import type { MS_Level } from '@/utils/ms_const';

const props = defineProps({
    rows: { type: Array as PropType<PBRankingPlayer[]>, required: true },
    level: { type: String as PropType<MS_Level>, required: true },
    bv: { type: Number, required: true },
    first: { type: Number, required: true },
    loading: { type: Boolean, required: true },
    colored: { type: Boolean, default: false },
});

function cellStyle(row: PBRankingPlayer, stat: PBStat) {
    if (!props.colored) return undefined;
    const value = Number(formatPBValue(row.timems, props.level, props.bv, stat));
    return colorThemes[getPiecewiseColorSchemeName(stat, props.level)].value.getStyle(value);
}

function previewVideo(row: PBRankingPlayer) {
    preview(row.video_id);
}

const { t } = useI18n();
</script>

<style scoped>
.pb-ranking-row {
    cursor: pointer;
}

.pb-ranking-row:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: -2px;
}
</style>
