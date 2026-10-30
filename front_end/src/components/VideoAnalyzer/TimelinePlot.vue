<template>
    <div ref="plot" class="timeline-plot" :class="{ 'timeline-plot--ruler': ruler, 'timeline-plot--pannable': ruler && canDrag }" @pointermove="hoverAt($event.clientX)" @pointerleave="hoverMs = null; emit('eventLeave')" @wheel="onWheel">
        <TransformGroup :domain="domain" :size="size" :padding="padding">
            <template v-if="ruler">
                <Axis direction="horizontal" :ticks="rulerTicks" :position="0" :offset="-10" :tick-size="rulerTickSizes">
                    <template #tick="{ tick }">
                        <tspan v-if="xTicks.includes(tick)" class="timeline-plot__time-label" :text-anchor="tick === xTicks[0] ? 'start' : tick === xTicks[xTicks.length - 1] ? 'end' : 'middle'">
                            {{ formatTick(tick / 1000) }}
                        </tspan>
                        <tspan v-else />
                    </template>
                </Axis>
            </template>
            <template v-else-if="eventDefinition && eventData">
                <Axis class="timeline-plot__event-axis" direction="horizontal" :position="0.5" :stroke-opacity="0.5" />
                <Line v-for="(span, index) in visibleSpans" :key="index" class="timeline-plot__event-span" :points="[{ x: span.startMs, y: 0.5 }, { x: span.renderEndMs, y: 0.5 }]" :stroke-color="eventDefinition.color" :stroke-width="eventDefinition.line.width" :stroke-opacity="eventDefinition.line.opacity" line-cap="round" :style="{ clipPath: plotClip, strokeDasharray: eventLineDash(eventDefinition.line.style) }" />
                <Scatter class="timeline-plot__event-pulses" :points="pulsePoints" :style="{ clipPath: plotClip }" interactive>
                    <template #point="{ point }">
                        <EventMarker :x="0" :y="0" :color="eventDefinition.color" :marker="{ shape: eventDefinition.marker.shape, opacity: eventDefinition.marker.opacity, size: 8 }" @pointerenter="emit('eventEnter', { key: eventDefinition.key, type: 'pulse', pulse: point.data }, $event)" @pointermove="emit('eventMove', $event)" @pointerleave="emit('eventLeave')" />
                    </template>
                </Scatter>
            </template>
            <template v-else>
                <Grid :x-ticks="xTicks" :y-ticks="yTicks" stroke-color="var(--ui-border-color)" :stroke-opacity="0.6" />
                <Line v-for="(track, index) in plottedTracks" :key="index" class="timeline-plot__line" :points="track.points" sampling="min-max" :stroke-color="track.color" :stroke-width="1.5" :style="{ clipPath: plotClip }" />
                <Axis class="timeline-plot__y-axis" direction="vertical" :ticks="yTicks" :position="domain.xMin" text-anchor="start" :offset="4" />
            </template>
        </TransformGroup>
        <svg v-if="eventDefinition && eventData" class="timeline-plot__event-hits" :width="size.width" :height="size.height" :viewBox="`0 0 ${size.width} ${size.height}`" :style="{ clipPath: plotClip }" aria-hidden="true">
            <line v-for="(span, index) in visibleSpans" :key="index" class="timeline-plot__event-span-hit" :x1="scaleX(span.startMs)" :x2="scaleX(span.renderEndMs)" :y1="scaleY(0.5)" :y2="scaleY(0.5)" :stroke-width="Math.max(8, eventDefinition.line.width)" @pointerenter="emit('eventEnter', { key: eventDefinition.key, type: 'sustained', span }, $event)" @pointermove="emit('eventMove', $event)" @pointerleave="emit('eventLeave')" />
        </svg>
        <svg class="timeline-plot__overlay" :width="size.width" :height="size.height" :viewBox="`0 0 ${size.width} ${size.height}`" :style="{ clipPath: plotClip }" aria-hidden="true">
            <rect v-if="rangeVisible" class="timeline-plot__range" :x="scaleX(playback.rangeStartMs.value)" :y="area.y" :width="scaleX(playback.rangeEndMs.value) - scaleX(playback.rangeStartMs.value)" :height="area.height" />
            <line v-if="rangeVisible" class="timeline-plot__range-start" :x1="scaleX(playback.rangeStartMs.value)" :x2="scaleX(playback.rangeStartMs.value)" :y1="area.y" :y2="area.y + area.height" />
            <line v-if="rangeVisible" class="timeline-plot__range-end" :x1="scaleX(playback.rangeEndMs.value)" :x2="scaleX(playback.rangeEndMs.value)" :y1="area.y" :y2="area.y + area.height" />
            <line class="timeline-plot__current" :x1="scaleX(playback.currentMs.value)" :x2="scaleX(playback.currentMs.value)" :y1="area.y" :y2="area.y + area.height" />
            <line v-if="hoverMs !== null" class="timeline-plot__hover" :x1="scaleX(hoverMs)" :x2="scaleX(hoverMs)" :y1="area.y" :y2="area.y + area.height" />
            <template v-if="!ruler && hoverMs !== null">
                <circle v-for="(point, index) in hoverPoints" :key="index" :cx="scaleX(hoverMs)" :cy="scaleY(point.value)" r="3" :fill="point.color" />
            </template>
        </svg>
        <output v-if="ruler && hoverMs !== null" class="timeline-plot__hover-time">{{ (hoverMs / 1000).toFixed(3) }} s</output>
        <div v-if="!ruler && !eventDefinition && hoverMs !== null" class="timeline-plot__values">
            <output v-for="(track, index) in hoverValues" :key="index" :title="track.text" :class="{ 'text-danger': track.error }">
                <i :style="{ backgroundColor: track.color }" />{{ track.key }}: {{ track.text }}
            </output>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@putianyi888/vue3-plots/style.css';
import type { DragEvent, PointerEvent as InteractPointerEvent } from '@interactjs/types';
import { Axis, createLinearScale, formatTick, getNiceTicks, getPlotArea, Grid, Line, Scatter, TransformGroup } from '@putianyi888/vue3-plots';
import type { PlotPoint } from '@putianyi888/vue3-plots';
import { useElementSize, useEventListener } from '@vueuse/core';
import interact from 'interactjs';
import { computed, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';

import { counterValue, displayCounter } from './counter';
import type { PreparedCounter } from './counter';
import { eventLineDash } from './customEvents';
import type { CustomEventDefinition, EventPulse, PreparedCustomEvent } from './customEvents';
import EventMarker from './EventMarker.vue';
import { panTimeWindow, timeAtPixel, timelinePadding, timelinePoints, timelineYDomain, zoomTimeWindow } from './timeline';
import type { TimelineTrack, TimeWindow } from './timeline';
import type { HoveredCustomEvent } from './useEventTooltip';
import type { PlaybackController } from './usePlayback';

const props = defineProps({
    playback: { type: Object as PropType<PlaybackController>, required: true },
    counters: { type: Object as PropType<Map<string, PreparedCounter>>, required: true },
    tracks: { type: Array as PropType<TimelineTrack[]>, default: () => [] },
    ruler: { type: Boolean, default: false },
    eventDefinition: { type: Object as PropType<CustomEventDefinition | null>, default: null },
    eventData: { type: Object as PropType<PreparedCustomEvent | null>, default: null },
});
const emit = defineEmits<{ eventEnter: [event: HoveredCustomEvent, pointer: PointerEvent]; eventMove: [pointer: PointerEvent]; eventLeave: [] }>();
const timeWindow = defineModel<TimeWindow>('window', { required: true });
const hoverMs = defineModel<number | null>('hoverMs', { default: null });
const plot = useTemplateRef<HTMLDivElement>('plot');
const { width, height } = useElementSize(plot);
const size = computed(() => ({ width: width.value, height: height.value }));
const padding = computed(() => (props.ruler ? { ...timelinePadding, top: 2, bottom: 2 } : timelinePadding));
const area = computed(() => getPlotArea(size.value, padding.value));
const yDomain = computed(() => (props.ruler || props.eventDefinition !== null ? { yMin: 0, yMax: 1 } : timelineYDomain(props.tracks, props.counters)));
const domain = computed(() => ({ xMin: timeWindow.value.startMs, xMax: timeWindow.value.endMs, ...yDomain.value }));
const scaleX = computed(() => createLinearScale(domain.value.xMin, domain.value.xMax, area.value.x, area.value.x + area.value.width));
const scaleY = computed(() => createLinearScale(domain.value.yMin, domain.value.yMax, area.value.y + area.value.height, area.value.y));
const xTicks = computed(() => getNiceTicks(domain.value.xMin, domain.value.xMax, Math.max(2, Math.floor(area.value.width / 100))));
const rulerTicks = computed(() => [...new Set([...xTicks.value, ...getNiceTicks(domain.value.xMin, domain.value.xMax, Math.max(2, Math.floor(area.value.width / 20)))])].sort((a, b) => a - b));
const rulerTickSizes = computed(() => rulerTicks.value.map((tick) => (xTicks.value.includes(tick) ? 4 : 2)));
const yTicks = computed(() => getNiceTicks(domain.value.yMin, domain.value.yMax, Math.max(2, Math.floor(area.value.height / 40))));
const plotClip = computed(() => `inset(${padding.value.top}px ${padding.value.right}px ${padding.value.bottom}px ${padding.value.left}px)`);
const rangeVisible = computed(() => props.playback.rangeStartMs.value !== 0 || props.playback.rangeEndMs.value !== props.playback.durationMs.value);
const visibleSpans = computed(() => props.eventData?.spans.filter((span) => span.renderEndMs >= timeWindow.value.startMs && span.startMs <= timeWindow.value.endMs) ?? []);
const pulsePoints = computed<PlotPoint<EventPulse>[]>(() => props.eventData?.pulses.filter((pulse) => pulse.timeMs >= timeWindow.value.startMs && pulse.timeMs <= timeWindow.value.endMs).map((pulse) => ({ x: pulse.timeMs, y: 0.5, data: pulse })) ?? []);
watch([() => props.eventData, () => props.eventDefinition, () => timeWindow.value.startMs, () => timeWindow.value.endMs, width, height], () => {
    emit('eventLeave');
});
const plottedTracks = computed(() => props.tracks.flatMap((track) => {
    const counter = props.counters.get(track.key);
    return counter === undefined ? [] : [{ ...track, counter, points: timelinePoints(counter, props.playback.durationMs.value) }];
}));
const hoverValues = computed(() => {
    const ms = hoverMs.value;
    if (ms === null) return [];
    return plottedTracks.value.map((track) => {
        const displayed = displayCounter(track.counter, ms);
        return { key: track.key, color: track.color, text: displayed.value, error: displayed.error };
    });
});
const hoverPoints = computed(() => {
    const ms = hoverMs.value;
    if (ms === null) return [];
    return plottedTracks.value.flatMap((track) => {
        if (track.counter.error !== '' || track.counter.samples.length === 0) return [];
        const value = counterValue(track.counter.samples, ms);
        return Number.isFinite(value) ? [{ color: track.color, value }] : [];
    });
});
const canDrag = computed(() => props.playback.durationMs.value > 0 && (!props.ruler || timeWindow.value.endMs - timeWindow.value.startMs < props.playback.durationMs.value));
let dragging = false;
let dragInteraction: DragEvent['interaction'] | null = null;

function timeAt(clientX: number) {
    const left = plot.value?.getBoundingClientRect().left ?? 0;
    return timeAtPixel(timeWindow.value, clientX - left, area.value.x, area.value.width);
}

function hoverAt(clientX: number) {
    if (props.playback.durationMs.value > 0) hoverMs.value = timeAt(clientX);
}

function onWheel(event: WheelEvent) {
    emit('eventLeave');
    if (!props.ruler || event.ctrlKey || event.metaKey || dragging || props.playback.durationMs.value <= 0 || area.value.width <= 0) return;
    event.preventDefault();
    const delta = (event.deltaY || event.deltaX) * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? area.value.width : 1);
    const span = timeWindow.value.endMs - timeWindow.value.startMs;
    const anchor = span > 0 ? (timeAt(event.clientX) - timeWindow.value.startMs) / span : 0.5;
    timeWindow.value = zoomTimeWindow(timeWindow.value, Math.exp(Math.max(-1, Math.min(1, delta * 0.002))), anchor, props.playback.durationMs.value);
    hoverAt(event.clientX);
}

function endDrag() {
    if (!dragging) return;
    dragging = false;
    dragInteraction = null;
    if (!props.ruler) props.playback.endSeek();
}

watch([plot, canDrag], ([element, enabled], _old, onCleanup) => {
    if (element === null) return;
    const target = interact(element).draggable({ enabled,
        lockAxis: 'x',
        startAxis: 'x',
        listeners: {
            start: (event: DragEvent) => {
                dragging = true;
                dragInteraction = event.interaction;
                if (!props.ruler) {
                    props.playback.beginSeek();
                    props.playback.seek(timeAt(event.clientX0));
                }
            },
            move: (event: DragEvent) => {
                if (props.ruler) {
                    if (area.value.width > 0) timeWindow.value = panTimeWindow(timeWindow.value, -event.delta.x / area.value.width * (timeWindow.value.endMs - timeWindow.value.startMs), props.playback.durationMs.value);
                } else props.playback.seek(timeAt(event.client.x));
                hoverAt(event.client.x);
            },
            end: endDrag,
        } }).on('tap', (event: InteractPointerEvent) => {
        if (!props.ruler && props.playback.durationMs.value > 0) props.playback.seek(timeAt(event.clientX));
    });
    onCleanup(() => {
        dragInteraction?.stop();
        endDrag();
        target.unset();
    });
}, { flush: 'post', immediate: true });

useEventListener('blur', () => {
    dragInteraction?.stop();
    endDrag();
});
useEventListener('pointercancel', () => {
    dragInteraction?.stop();
    endDrag();
});
</script>

<style scoped>
.timeline-plot {
    position: relative;
    min-width: 0;
    min-height: 0;
    height: 100%;
    overflow: hidden;
    color: var(--ui-text-color-regular);
    touch-action: none;
    user-select: none;
    cursor: crosshair;
    font-size: 11px;
}

.timeline-plot--ruler {
    cursor: default;
}

.timeline-plot--pannable {
    cursor: grab;
}

.timeline-plot--pannable:active {
    cursor: grabbing;
}

.timeline-plot__overlay {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
}

.timeline-plot__event-hits {
    position: absolute;
    inset: 0;
    pointer-events: none;
}

.timeline-plot__event-span-hit {
    pointer-events: stroke;
    stroke: transparent;
    stroke-linecap: round;
    cursor: help;
}

.timeline-plot__overlay line {
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
}

.timeline-plot__range {
    fill: var(--ui-color-primary);
    fill-opacity: 0.07;
}

.timeline-plot__range-start,
.timeline-plot__range-end {
    stroke: var(--ui-color-warning);
    stroke-dasharray: 3 3;
}

.timeline-plot__current {
    stroke: var(--ui-color-primary);
    stroke-width: 2 !important;
}

.timeline-plot__hover {
    stroke: var(--ui-text-color-secondary);
    stroke-dasharray: 2 2;
}

.timeline-plot__values {
    position: absolute;
    top: 8px;
    right: 6px;
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 2px 8px;
    max-width: calc(100% - 12px);
    max-height: calc(100% - 16px);
    overflow: hidden;
    pointer-events: none;
    background: var(--ui-bg-color);
}

.timeline-plot__values output {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}

.timeline-plot__y-axis :deep(text) {
    paint-order: stroke;
    stroke: var(--ui-bg-color);
    stroke-width: 3px;
    stroke-linejoin: round;
}

.timeline-plot__values i {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 4px;
}

.timeline-plot__hover-time {
    position: absolute;
    top: 0;
    right: 4px;
    background: var(--ui-bg-color);
    pointer-events: none;
    font-variant-numeric: tabular-nums;
}
</style>
