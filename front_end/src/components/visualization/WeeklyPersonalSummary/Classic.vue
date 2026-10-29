<template>
    <div class="text-large text-regular">
        {{ t('level.sum') }}{{ t('punct.colon') }}{{ ms_to_s(iSum + eSum) }}
    </div>
    <div class="text-large text-regular" style="margin-top: 0.5em">
        {{ t('level.e') }}{{ t('punct.colon') }}{{ ms_to_s(eSum) }}
    </div>
    <div class="cell-list">
        <VideoCell v-for="i in 2" :key="`e${i}`" class="cell" :video="bestE[i-1]" :text="getCellText(bestE[i-1], 240)" :value="getCellValue(bestE[i-1], 240)" :color-theme="colorThemes.etime.value" />
    </div>
    <div class="text-large text-regular" style="margin-top: 0.5em">
        {{ t('level.i') }}{{ t('punct.colon') }}{{ ms_to_s(iSum) }}
    </div>
    <div class="cell-list">
        <VideoCell v-for="i in 5" :key="`i${i}`" class="cell" :video="bestI[i-1]" :text="getCellText(bestI[i-1], 60)" :value="getCellValue(bestI[i-1], 60)" :color-theme="colorThemes.itime.value" />
    </div>
</template>

<script setup lang="ts">

import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import VideoCell from '@/components/visualization/VideoCell.vue';
import { colorThemes } from '@/store/color';
import { ms_to_s } from '@/utils';
import { MS_Mode, MS_State } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    videos: { type: Array<VideoAbstract>, default: () => [] },
});

const { t } = useI18n();

function bestVideos(videos: VideoAbstract[], level: 'i' | 'e') {
    const filtered = videos.filter((video) => video.state === MS_State.Official && video.level === level && video.mode === MS_Mode.Standard);
    const sorted = filtered.sort((v1, v2) => v1.timems - v2.timems);
    if (level === 'i') return sorted.slice(0, 5);
    return sorted.slice(0, 2);
}

function getCellText(video: VideoAbstract | undefined, defaultTime: number): string {
    return video?.displayStat('time') ?? String(defaultTime);
}

function getCellValue(video: VideoAbstract | undefined, defaultTime: number): number {
    return video?.time ?? defaultTime;
}

const bestI = computed(() => bestVideos(props.videos, 'i'));
const bestE = computed(() => bestVideos(props.videos, 'e'));

const iSum = computed(() => bestI.value.reduce((sum, video) => sum + video.timems, 0) + 60000 * (5 - bestI.value.length));
const eSum = computed(() => bestE.value.reduce((sum, video) => sum + video.timems, 0) + 240000 * (2 - bestE.value.length));
</script>

<style lang="less" scoped>
@import './cell.less';

.cell-list {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
}
</style>
