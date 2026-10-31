<template>
    <div ref="scatterRef" class="video-scatter" :class="{ 'is-fullscreen': isFullscreen }">
        <Toolbar :is-fullscreen="isFullscreen" @toggle-fullscreen="toggle" />
        <div class="video-scatter-canvas">
            <Canvas />
        </div>
    </div>
</template>

<script setup lang="ts">
import { useFullscreen } from '@vueuse/core';
import { useTemplateRef, watch } from 'vue';

import Canvas from './Canvas.vue';
import { VideoScatterStore } from './store';
import Toolbar from './Toolbar.vue';

import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    videos: { type: Array<VideoAbstract>, default: () => [] },
});

const scatterRef = useTemplateRef<HTMLDivElement>('scatterRef');
const { isFullscreen, toggle } = useFullscreen(scatterRef);

type TippyHost = HTMLElement & { _tippy?: { hide: () => void } };

// tippy 隐藏时会卸载浮层，下次显示再按 appendTo 重新挂载（见 Canvas / MarkerSetting）。
// 因此全屏切换只需收起已展开的浮层：留在 body 上的浮层不会进入全屏绘制子树，
// 而新展开的浮层会自动挂到全屏元素内。
watch(isFullscreen, () => {
    const root = scatterRef.value;
    if (!root) return;
    root.querySelectorAll<TippyHost>('.video-scatter-tippy, .marker-setting-tippy').forEach((element) => {
        element._tippy?.hide();
    });
});

watch(() => props.videos, (videos) => {
    VideoScatterStore.setRawData(videos);
}, { immediate: true });
</script>

<style lang="less" scoped>
.video-scatter {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    gap: 1em;
    height: 600px;
}

.video-scatter.is-fullscreen {
    background: var(--ui-bg-color);
    box-sizing: border-box;
    height: 100vh;
    padding: 1em;
    width: 100vw;
}

.video-scatter-canvas {
    display: flex;
    flex: 1 1 auto;
    min-height: 0;
}
</style>
