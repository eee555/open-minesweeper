<template>
    <div ref="container" class="masonry-layout" :data-layout-version="layoutVersion">
        <slot />
    </div>
</template>

<script setup lang="ts">
import { MasonryGrid } from '@egjs/grid';
import { useResizeObserver } from '@vueuse/core';
import { onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue';

const props = defineProps({ minimumColumnWidth: { type: Number, default: 304 } });
defineSlots<{ default?: () => unknown }>();

const gap = 16;
const container = useTemplateRef<HTMLDivElement>('container');
const layoutVersion = ref(0);
let grid: MasonryGrid | null = null;

function columnCount(element: HTMLElement) {
    return Math.max(1, Math.min(element.childElementCount, Math.floor((element.clientWidth + gap) / (props.minimumColumnWidth + gap))));
}

function updateColumns() {
    if (container.value === null || grid === null) return;
    const columns = columnCount(container.value);
    if (grid.column === columns) return;
    grid.column = columns;
    grid.renderItems({ useResize: true });
}

useResizeObserver(container, updateColumns);
watch(() => props.minimumColumnWidth, updateColumns);

onMounted(() => {
    if (container.value === null) return;
    grid = new MasonryGrid(container.value, {
        align: 'stretch',
        column: columnCount(container.value),
        gap,
        useResizeObserver: true,
        observeChildren: true,
        useRoundedSize: false,
        renderOnPropertyChange: false,
    });
    grid.on('renderComplete', () => {
        layoutVersion.value++;
    });
    grid.renderItems();
});

onBeforeUnmount(() => {
    grid?.off();
    grid?.destroy();
    grid = null;
});
</script>

<style scoped>
.masonry-layout {
    position: relative;
    min-width: 0;
}
.masonry-layout > :deep(*) {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
}
</style>
