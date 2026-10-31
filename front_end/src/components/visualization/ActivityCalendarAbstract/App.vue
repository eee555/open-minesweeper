<template>
    <BaseCardNormal style="overflow: auto;">
        <div class="layout-row" style="align-items: center; margin-bottom: 5px;">
            <Header data-cy="header" :video-list="videoList" />
        </div>
        <div class="layout-row">
            <DayLabel data-cy="dayLabel" :cell-size="options.cellSize" :cell-margin="options.cellMargin" />
            <ElScrollbar style="flex:1;">
                <div class="layout-row" :style="{ height: `${cellFullSize}px` }">
                    <MonthLabel :start-date="startDate" :end-date="endDate" :cell-size="options.cellSize" :cell-margin="options.cellMargin" />
                </div>
                <div class="layout-row" :style="{ height: `${cellFullSize * 7 + options.cellMargin}px` }">
                    <Tippy
                        :duration="0"
                        sticky
                        follow-cursor
                        :style="{
                            height: '100%',
                            display: 'grid',
                            gridTemplateRows: 'repeat(7, 1fr)',
                            gridAutoFlow: 'column',
                            gap: `${options.cellMargin}px`,
                        }"
                    >
                        <!-- 为每个日期生成一个单元格 -->
                        <div v-if="startDate.getDay() > 0" :style="{gridRowStart: `${startDate.getDay()}`}" />
                        <component
                            :is="selectable ? 'button' : 'div'"
                            v-for="cell of dateCells"
                            :key="cell.dateKey"
                            class="calendar-cell text-regular"
                            :class="{ 'is-selectable': selectable, 'is-selected': selectable && selectedDateKey === cell.dateKey }"
                            :type="selectable ? 'button' : undefined"
                            :aria-label="selectable ? `${cell.dateKey}: ${cell.videos.length}` : undefined"
                            :aria-pressed="selectable ? selectedDateKey === cell.dateKey : undefined"
                            :style="{
                                width: `${options.cellSize}px`,
                                height: `${options.cellSize}px`,
                                fontSize: `${options.cellSize * 0.6}px`,
                            }"
                            :data-cy="`cell-${cell.dateKey}`"
                            @mouseover="tooltipVideos = cell.videos; tooltipDate = cell.date"
                            @focus="tooltipVideos = cell.videos; tooltipDate = cell.date"
                            @click="selectable && emit('selectDate', cell.dateKey)"
                        >
                            <MiniPie
                                v-if="cell.pieData.length > 0"
                                class="mini-pie"
                                :data="cell.pieData"
                                :radius="options.cellSize / 2"
                                :stroke-width="0"
                            />
                            <span v-if="options.showDate" class="date-label">
                                {{ cell.date.getDate() }}
                            </span>
                        </component>
                        <template #content>
                            <Tooltip :date="tooltipDate" :videos="tooltipVideos" />
                        </template>
                    </Tippy>
                </div>
            </ElScrollbar>
        </div>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import '@/styles/layout.css';

import { MiniPie } from '@putianyi888/vue3-plots';
import type { PieDatum } from '@putianyi888/vue3-plots';
import { ElScrollbar } from 'element-plus';
import type { PropType } from 'vue';
import { computed, ref } from 'vue';
import { Tippy } from 'vue-tippy';

import DayLabel from './DayLabel.vue';
import Header from './Header.vue';
import MonthLabel from './MonthLabel.vue';
import Tooltip from './Tooltip.vue';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { colorTheme } from '@/store';
import { generateDateRange, toISODateString } from '@/utils/datetime';
import { isStandardLevel } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';
import { groupVideosByDate } from '@/utils/videoabstract';

interface Options {
    cellSize: number;
    cellMargin: number;
    showDate: boolean;
    useEndTime: boolean;
}

const props = defineProps({
    selectable: { type: Boolean, default: false },
    selectedDateKey: { type: String, default: undefined },
    videoList: {
        type: Array<VideoAbstract>,
        default: () => [],
    },
    options: {
        type: Object as PropType<Options>,
        default: () => {
            return {
                cellSize: 14,
                cellMargin: 3,
                showDate: true,
                useEndTime: false,
            };
        },
    },
});
const emit = defineEmits<{ selectDate: [dateKey: string] }>();

const tooltipVideos = ref([] as VideoAbstract[]);
const tooltipDate = ref(new Date());

const cellFullSize = computed(() => props.options.cellSize + props.options.cellMargin);

const groupedVideoAbstract = computed(() => groupVideosByDate(props.videoList, props.options.useEndTime ? 'end_time' : 'upload_time'));
const endDate = new Date(new Date().toDateString()); // today
const startDate = computed(() => {
    const keys = groupedVideoAbstract.value.keys();
    let min = new Date(endDate);
    min.setFullYear(min.getFullYear() - 1);
    min.setDate(min.getDate() + 1);
    for (const key of keys) {
        const keydate = new Date(`${key}T00:00:00`);
        if (keydate < min) min = keydate;
    }
    return min;
});

const dateRange = computed(() => Array.from(generateDateRange(startDate.value, endDate, 1)));
const dateCells = computed(() => dateRange.value.map((date) => {
    const dateKey = toISODateString(date);
    const videos = groupedVideoAbstract.value.get(dateKey) ?? [];
    return {
        date,
        dateKey,
        videos,
        pieData: getPieData(videos),
    };
}));

function getPieData(videos: VideoAbstract[]): PieDatum[] {
    const count = { b: 0, i: 0, e: 0, c: 0 };
    for (const video of videos) {
        if (isStandardLevel(video.level)) count[video.level]++;
        else count.c++;
    }
    return [
        { value: count.b, color: colorTheme.value.level.b },
        { value: count.i, color: colorTheme.value.level.i },
        { value: count.e, color: colorTheme.value.level.e },
        { value: count.c, color: colorTheme.value.level.c },
    ].filter((data) => data.value > 0);
}
</script>

<style scoped>
.calendar-cell {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
}

.calendar-cell.is-selectable {
    padding: 0;
    border: 0;
    background: transparent;
    font: inherit;
    cursor: pointer;
}

.calendar-cell.is-selected {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 0;
    z-index: 1;
}

.calendar-cell:focus-visible {
    box-shadow: 0 0 0 3px var(--ui-text-color-primary);
}

.mini-pie {
    position: absolute;
    inset: 0;
}

.date-label {
    position: relative;
    z-index: 1;
}
</style>
