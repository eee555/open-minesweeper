<template>
    <VideoPreviewLink v-if="video" :id="video.id" :video="video" :style="cellStyle" class="video-cell-action" data-cy="video-cell-action">
        {{ text }}
    </VideoPreviewLink>
    <span v-else :style="cellStyle">
        {{ text }}
    </span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { computed } from 'vue';

import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { PiecewiseColorScheme } from '@/utils/colors';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    video: { type: Object as PropType<VideoAbstract | undefined>, default: undefined },
    text: { type: String, default: '' },
    value: { type: Number, default: NaN },
    colorTheme: { type: Object as PropType<PiecewiseColorScheme>, default: new PiecewiseColorScheme([], []) },
});

const cellStyle = computed(() => props.colorTheme.getStyle(props.value));
</script>

<style lang="less" scoped>
.video-cell-action:hover,
.video-cell-action:active {
    color: inherit;
}
</style>
