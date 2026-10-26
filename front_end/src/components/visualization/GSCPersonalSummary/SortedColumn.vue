<template>
    <div class="cell text-regular">
        {{ t(`prop.${sortBy}`) }}
    </div>
    <VideoCell v-for="video in sortedVideos" :key="video.id" class="cell" :video="video" :text="video.displayStat(sortBy)" :value="video[sortBy]" :color-theme="colorScheme" />
    <VideoCell v-for="i in count - sortedVideos.length" :key="`default-${i}`" class="cell" :text="defaultStatText" :value="defaultStat" :color-theme="colorScheme" />
    <div class="cell" :style="colorScheme.getStyle(avgStat)">
        {{ formatNumberSmart(sumStat, 6, 3) }}
    </div>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import { sum } from 'd3-array';
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { defaultVideos } from './utils';

import VideoCell from '@/components/visualization/VideoCell.vue';
import { colorThemes } from '@/store/color';
import type { MS_Level } from '@/utils/ms_const';
import { formatNumberSmart } from '@/utils/strings';
import type { StandardVideoAbstract } from '@/utils/videoabstract';

type sortByOptions = 'time' | 'bvs' | 'stnb';

const props = defineProps({
    videos: { type: Array as PropType<StandardVideoAbstract[]>, default: () => [] },
    level: { type: String as PropType<MS_Level>, required: true },
    sortBy: { type: String as PropType<sortByOptions>, required: true },
    count: { type: Number, required: true },
});

const { t } = useI18n();

const colorScheme = computed(() => {
    switch (props.sortBy) {
        case 'time':
            return colorThemes[`${props.level}time`].value;
        case 'bvs':
            return colorThemes.bvs.value;
        case 'stnb':
            return colorThemes.stnb.value;
    }
});

const _videos = computed(() => props.videos.filter((video) => !isNaN(video[props.sortBy])));

const sortedVideos = computed(() => {
    const sorted = Array.from(_videos.value).sort((v1, v2) => v1[props.sortBy] - v2[props.sortBy]);
    if (props.sortBy === 'time') {
        return sorted.slice(0, props.count);
    } else {
        return sorted.slice(-props.count).reverse();
    }
});

const sumStat = computed(() => {
    if (props.sortBy === 'time') {
        const totalMs = sum(sortedVideos.value, (video) => video.timems) + (props.count - sortedVideos.value.length) * defaultVideos[props.level].time * 1000;
        return totalMs / 1000;
    }
    return sum(sortedVideos.value, (video) => video[props.sortBy]) + (props.count - sortedVideos.value.length) * defaultVideos[props.level][props.sortBy];
});

const avgStat = computed(() => sumStat.value / props.count);
const defaultStat = computed(() => defaultVideos[props.level][props.sortBy]);
const defaultStatText = computed(() => String(defaultStat.value));

defineExpose({ sumStat });
</script>

<style lang="less" scoped>
@import './cell.less';
</style>
