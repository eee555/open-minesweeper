<template>
    <Tippy class="video-scatter-tippy" :duration="0" sticky follow-cursor :append-to="appendTo">
        <YLabel class="text">
            {{ t(`prop.${VideoScatterConfig.y}`) }}
        </YLabel>
        <div ref="plotRef" class="plot-stage">
            <TransformGroup
                :domain="VideoScatterStore.plotDomain"
                :padding="VideoScatterStore.plotPadding"
                :size="VideoScatterStore.plotSize"
            >
                <Grid :stroke-color="gridColor" :x-ticks="xTicks" :y-ticks="yTicks" />
                <HighlightSelected v-if="VideoScatterConfig.highlightSelected" />
                <Scatter
                    :points="VideoScatterStore.scatterData.points"
                    :fill-color="VideoScatterStore.fillColor"
                    :radius="VideoScatterConfig.radius"
                    :stroke-color="VideoScatterStore.fillColor"
                    :stroke-width="VideoScatterStore.strokeWidth"
                    :stroke-opacity="0.5"
                    interactive
                    @point-click="handlePointClick"
                    @point-enter="handlePointEnter"
                    @point-leave="activePoint = null;"
                />
                <Axis direction="horizontal" :ticks="xTicks" :style="{ color: axisColor }" />
                <Axis direction="vertical" :ticks="yTicks" :style="{ color: axisColor }" />
                <MouseDraw
                    :mode="VideoScatterStore.canvasMode == 'select' ? 'rect' : ''"
                    @draw="handleDraw"
                />
            </TransformGroup>
        </div>
        <span />
        <XLabel class="text">
            {{ t(`prop.${VideoScatterConfig.x}`) }}
        </XLabel>

        <template #content>
            <div v-if="activePoint" class="card card-small">
                <VideoAbstractDisplay :video="activePoint.data" />
            </div>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@putianyi888/vue3-plots/style.css';

import { Axis, createLinearScale, Ellipse, getNiceTicks, getPlotArea, Grid, MouseDraw, Rect, Scatter, TransformGroup, XLabel, YLabel } from '@putianyi888/vue3-plots';
import type { AnyShape, PlotPoint } from '@putianyi888/vue3-plots';
import { useResizeObserver } from '@vueuse/core';
import { computed, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import HighlightSelected from './HighlightSelected.vue';
import { VideoScatterStore } from './store';

import VideoAbstractDisplay from '@/components/widgets/VideoAbstractDisplay.vue';
import { VideoScatterConfig } from '@/store';
import { getTextColor } from '@/utils/colors';
import { preview } from '@/utils/common/PlayerDialog';
import type { VideoAbstract } from '@/utils/videoabstract';

const plotRef = useTemplateRef<HTMLDivElement>('plotRef');
const activePoint = ref<PlotPoint<VideoAbstract> | null>(null);

const xTicks = computed(() => getNiceTicks(VideoScatterStore.plotDomain.xMin, VideoScatterStore.plotDomain.xMax, 5));
const yTicks = computed(() => getNiceTicks(VideoScatterStore.plotDomain.yMin, VideoScatterStore.plotDomain.yMax, 5));

const axisColor = computed(() => getTextColor('regular'));
const gridColor = computed(() => getComputedStyle(document.documentElement).getPropertyValue('--ui-border-color-lighter'));

function handlePointClick(point: PlotPoint<VideoAbstract>) {
    if (point.data.isLocal) return;
    void preview(point.data.id, point.data.software);
}

function handlePointEnter(point: PlotPoint<VideoAbstract>) {
    activePoint.value = point;
}

// 全屏时必须挂进全屏元素子树，否则浮层不绘制；非全屏仍挂 body，
// 避免被祖先元素的 overflow 裁剪。
function appendTo(element: Element) {
    const fullscreenEl = document.fullscreenElement;
    return fullscreenEl?.contains(element) === true
        ? element.parentElement ?? fullscreenEl
        : document.body;
}

function handleDraw(shape: AnyShape) {
    VideoScatterStore.selectionDraw(shapeToData(shape));
}

function shapeToData(shape: AnyShape): AnyShape {
    if (shape.type === 'ellipse') return ellipseToData(shape);
    if (shape.type === 'rect') return rectToData(shape);
    return shape;
}

function rectToData(shape: Rect): Rect {
    const scaleX = createSvgToDataXScale();
    const scaleY = createSvgToDataYScale();
    const x1 = scaleX(shape.x);
    const x2 = scaleX(shape.x + shape.width);
    const y1 = scaleY(shape.y);
    const y2 = scaleY(shape.y + shape.height);

    return new Rect(
        Math.min(x1, x2),
        Math.min(y1, y2),
        Math.abs(x2 - x1),
        Math.abs(y2 - y1),
    );
}

function ellipseToData(shape: Ellipse): Ellipse {
    const scaleX = createSvgToDataXScale();
    const scaleY = createSvgToDataYScale();
    const cx = scaleX(shape.cx);
    const cy = scaleY(shape.cy);

    return new Ellipse(
        cx,
        cy,
        Math.abs(scaleX(shape.cx + shape.rx) - cx),
        Math.abs(scaleY(shape.cy + shape.ry) - cy),
    );
}

function createSvgToDataXScale() {
    const area = getPlotArea(VideoScatterStore.plotSize, VideoScatterStore.plotPadding);
    return createLinearScale(area.x, area.x + area.width, VideoScatterStore.plotDomain.xMin, VideoScatterStore.plotDomain.xMax);
}

function createSvgToDataYScale() {
    const area = getPlotArea(VideoScatterStore.plotSize, VideoScatterStore.plotPadding);
    return createLinearScale(area.y + area.height, area.y, VideoScatterStore.plotDomain.yMin, VideoScatterStore.plotDomain.yMax);
}

useResizeObserver(plotRef, ([entry]) => {
    VideoScatterStore.plotSize = {
        width: entry.contentRect.width,
        height: entry.contentRect.height,
    };
});

const { t } = useI18n();
</script>

<style lang="less" scoped>
.video-scatter-tippy {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    grid-template-columns: auto minmax(220px, 1fr);
    grid-template-rows: minmax(180px, 1fr) auto;
}

.plot-stage {
    height: 100%;
    overflow: hidden;
    position: relative;
    width: 100%;
}
</style>
