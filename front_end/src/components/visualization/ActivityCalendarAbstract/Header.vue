<template>
    <div data-cy="count" style="display: flex; width: 100%; align-items: center">
        <span class="text-regular text-small" style="margin-right: 0.5em">
            {{ t('local.totalNVideos', [videoList.length]) }}
        </span>
        <div style="flex-grow: 1;">
            <StackBar :data="videoCountData" />
        </div>
    </div>
    <div data-cy="size" style="display: flex; width: 100%; align-items: center">
        <span class="text-regular text-small" style="margin-right: 0.5em">
            {{ t('local.totalNBytes', [totalSize]) }}
        </span>
        <div style="flex-grow: 1;">
            <StackBar :data="videoFileSizeData" />
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import StackBar from '@/components/visualization/StackBar/App.vue';
import { colorTheme } from '@/store';
import { CustomLevel } from '@/utils/customlevel';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    videoList: {
        type: Array<VideoAbstract>,
        default: () => [],
    },
});

const levelGroups = ['b', 'i', 'e', 'c'] as const;
type LevelGroup = typeof levelGroups[number];

function getLevelGroup(video: VideoAbstract): LevelGroup {
    return video.level instanceof CustomLevel ? 'c' : video.level;
}

const levelStats = computed(() => {
    const stats = Object.fromEntries(levelGroups.map((level) => [
        level,
        { count: 0, size: 0 },
    ])) as Record<LevelGroup, { count: number; size: number }>;

    for (const video of props.videoList) {
        const level = getLevelGroup(video);
        stats[level].count++;
        stats[level].size += video.file_size;
    }

    return stats;
});

const totalSize = computed(() => levelStats.value.b.size + levelStats.value.i.size + levelStats.value.e.size + levelStats.value.c.size);

const videoCountData = computed(() => levelGroups.map((level) => ({
    name: t(`level.${level}`),
    value: levelStats.value[level].count,
    color: colorTheme.value.level[level],
})));

const videoFileSizeData = computed(() => levelGroups.map((level) => ({
    name: t(`level.${level}`),
    value: levelStats.value[level].size,
    color: colorTheme.value.level[level],
})));

const i18nMessages = {
    'zh-cn': { local: {
        totalNBytes: '占用{0}字节',
        totalNVideos: '共{0}个录像',
    } },
    en: { local: {
        totalNBytes: '{0} bytes',
        totalNVideos: '{0} videos in total',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="less">
.dot {
    height: 12px;
    width: 12px;
    border-radius: 50%;
    display: inline-block;
}
</style>
