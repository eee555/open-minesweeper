<template>
    <div v-if="header" class="layout-row" :style="{ textAlign: 'center', height: '25px', flexWrap: 'nowrap', marginTop: '10px', marginBottom: '-20px' }">
        <span style="width: 10%; min-width: 4em" />
        <span :style="gridStyle">
            <span v-for="i in 10" :key="i" class="text-regular text-small">
                {{ i - 1 }}
            </span>
        </span>
    </div>
    <div class="summary-heading" data-cy="summary">
        <span class="text-regular">
            {{ t(`level.${level}`) }}
            &nbsp;
            {{ t('BBBvSummary.bbbvInTotal', [groupedVideoAbstract.size]) }}
        </span>
    </div>
    <div v-if="groupedVideoAbstract.size > 0" class="layout-row" style="white-space: nowrap;">
        <YLabel :min-bv="minBv" :max-bv="maxBv" />
        <Tippy :duration="0" sticky follow-cursor :style="gridStyle">
            <Cell
                v-for="bv in ArrayUtils.range(minBv, maxBv)"
                :key="bv"
                :data-cy="`bv-${bv}`"
                :videos="groupedVideoAbstract.get(bv)"
                :color-theme="theme"
                :display-by="options[BBBvSummaryConfig.template].displayBy"
                :sort-by="options[BBBvSummaryConfig.template].sortBy"
                :sort-desc="options[BBBvSummaryConfig.template].sortDesc"
                :software-filter="BBBvSummaryConfig.softwareFilter"
                :selectable="selectable"
                :selected="selectedBV === bv"
                :selection-label="`${t(`level.${level}`)} BV ${bv}`"
                :show-icon="BBBvSummaryConfig.showIcon"
                :new-thresh="BBBvSummaryConfig.newThresh"
                :new-date-field="BBBvSummaryConfig.newDateField"
                @mouseover="tooltipVideos=groupedVideoAbstract.get(bv) || []"
                @focusin="tooltipVideos=groupedVideoAbstract.get(bv) || []"
                @select="emit('selectBV', { level, bv })"
            />
            <template #content>
                <Tooltip
                    :videos="tooltipVideos"
                    :sort-by="options[BBBvSummaryConfig.template].sortBy"
                    :sort-desc="options[BBBvSummaryConfig.template].sortDesc"
                    :software-filter="BBBvSummaryConfig.softwareFilter"
                />
            </template>
        </Tippy>
    </div>
</template>

<script setup lang="ts">
import '@/styles/layout.css';
import '@/styles/text.css';
import type { PropType } from 'vue';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import Cell from './Cell.vue';
import Tooltip from './Tooltip.vue';
import YLabel from './YLabel.vue';

import { BBBvSummaryConfig } from '@/store';
import { colorThemes } from '@/store/color';
import { ArrayUtils } from '@/utils/arrays';
import { PiecewiseColorScheme } from '@/utils/colors';
import { setLastDigit } from '@/utils/math';
import type { CellChoice, ColorTemplateName, MS_Level } from '@/utils/ms_const';
import { getPiecewiseColorSchemeName, PiecewiseColorSchemeName } from '@/utils/ms_const';
import type { getStat_stat, VideoAbstract } from '@/utils/videoabstract';
import { groupVideosByBBBv } from '@/utils/videoabstract';

const props = defineProps({
    selectable: { type: Boolean, default: false },
    selectedBV: { type: Number, default: undefined },
    header: { type: Boolean, default: false },
    level: { type: String as PropType<MS_Level>, required: true },
    videoList: { type: Array<VideoAbstract>, default: () => [] },
});
const emit = defineEmits<{ selectBV: [selection: { level: MS_Level; bv: number }] }>();
const { t } = useI18n();
const tooltipVideos = ref([] as VideoAbstract[]);

interface Option {
    value: ColorTemplateName;
    sortBy: getStat_stat;
    displayBy: CellChoice;
    label: string;
    sortDesc: boolean;
}

const options = computed(() => {
    return {
        bvs: { value: 'bvs', sortBy: 'timems', displayBy: 'bvs', label: 'bvs', sortDesc: false },
        time: { value: 'time', sortBy: 'timems', displayBy: 'time', label: 'time', sortDesc: false },
        stnb: { value: 'stnb', sortBy: 'timems', displayBy: 'stnb', label: 'stnb', sortDesc: false },
        ioe: { value: 'ioe', sortBy: 'ioe', displayBy: 'ioe', label: 'ioe', sortDesc: true },
        thrp: { value: 'thrp', sortBy: 'thrp', displayBy: 'thrp', label: 'thrp', sortDesc: true },
        path: { value: 'path', sortBy: 'path', displayBy: 'path', label: 'path', sortDesc: false },
        ces: { value: 'ces', sortBy: 'ces', displayBy: 'ces', label: 'ces', sortDesc: true },
        cls: { value: 'cls', sortBy: 'cls', displayBy: 'cls', label: 'cls', sortDesc: true },
        custom: { value: 'custom', sortBy: BBBvSummaryConfig.value.sortBy, displayBy: BBBvSummaryConfig.value.displayBy, label: 'custom', sortDesc: BBBvSummaryConfig.value.sortDesc },
    } as Record<ColorTemplateName, Option>;
});

const groupedVideoAbstract = computed(() => groupVideosByBBBv(props.videoList, props.level));
const maxBv = computed(() => setLastDigit(ArrayUtils.maximum(groupedVideoAbstract.value.keys()), 9));
const minBv = computed(() => setLastDigit(ArrayUtils.minimum(groupedVideoAbstract.value.keys()), 0));

const displayBy = computed(() => options.value[BBBvSummaryConfig.value.template].displayBy);

const theme = computed(() => {
    if (!(PiecewiseColorSchemeName as readonly string[]).includes(displayBy.value)) return new PiecewiseColorScheme([], []);
    const themeName = getPiecewiseColorSchemeName(displayBy.value as PiecewiseColorSchemeName, props.level);
    return colorThemes[themeName].value;
});

const gridStyle = computed(() => {
    return {
        display: 'grid',
        width: '89%',
        minWidth: BBBvSummaryConfig.value.showIcon === '' ? '37em' : '48em',
        gridTemplateColumns: 'repeat(10, 1fr)',
        gridAutoRows: '25px',
    };
});
</script>

<style lang="less" scoped>
.layout-row {
    flex-wrap: nowrap;
}

.summary-heading {
    display: flex;
    align-items: center;
    gap: 20px;
    margin: 8px 0 3px;
    line-height: 20px;
    font-weight: 500;
}

.summary-heading::before,
.summary-heading::after {
    content: '';
    flex: 1;
    border-top: 1px solid var(--ui-border-color);
}

.summary-heading > span {
    min-width: 0;
    text-align: center;
}
</style>
