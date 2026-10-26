<template>
    <figure class="top-radar" :data-nf="nf" :aria-label="title">
        <Tippy ref="tooltip" tag="div" trigger="manual" follow-cursor :duration="0">
            <svg class="top-radar-svg" viewBox="0 0 480 440" role="group" :aria-label="title" @mousemove="updateTooltip" @mouseleave="hovered = null">
                <g class="top-radar-decoration" aria-hidden="true">
                    <path v-for="(ring, index) in rings" :key="ring.seconds" class="top-radar-ring" :data-ring="index" :d="ring.path" :fill="ring.color" fill-opacity="0.16" fill-rule="evenodd" pointer-events="fill" />
                    <polygon v-for="ring in rings" :key="`grid-${ring.seconds}`" class="top-radar-grid" :points="ring.points" />
                    <line v-for="(row, index) in rows" :key="row.field" class="top-radar-axis" x1="240" y1="220" :x2="axisEnds[index].x" :y2="axisEnds[index].y" />
                    <polygon class="top-radar-anchor" :points="anchorPoints" :stroke="nf ? 'var(--ui-color-warning)' : 'var(--ui-color-primary)'" />
                    <polygon class="top-radar-player" :points="playerPoints" />
                    <circle v-for="(row, index) in rows" :key="`point-${row.field}`" class="top-radar-point" :cx="point(index, row.radius).x" :cy="point(index, row.radius).y" r="3" />
                    <text v-if="nf" class="top-radar-mark" x="240" y="220" text-anchor="middle" dominant-baseline="middle">NF</text>
                    <text v-for="(row, index) in rows" :key="`label-${row.field}`" class="top-radar-label" :x="labels[index].x" :y="labels[index].y - 5" :text-anchor="labels[index].anchor">
                        <tspan :x="labels[index].x">{{ t(`level.${row.level}`) }}</tspan>
                        <tspan :x="labels[index].x" dy="14">{{ t(`prop.${topStatNames[row.stat]}`) }}</tspan>
                    </text>
                </g>
                <line v-for="(row, index) in rows" :key="`hit-${row.field}`" class="top-radar-hit" :data-axis="index" x1="240" y1="220" :x2="axisEnds[index].x" :y2="axisEnds[index].y" tabindex="0" :aria-label="`${row.name}: ${tooltipText(index)}`" />
            </svg>
            <template #content>
                <div v-if="tooltipLines.length" class="card card-small top-radar-tooltip">
                    <div v-for="(line, index) in tooltipLines" :key="index">
                        {{ line }}
                    </div>
                </div>
            </template>
        </Tippy>
    </figure>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import { computed, ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import { formatTopValue, topAxes, topField, topGrade, topMean, topRadius, topStatNames } from '@/services/topRankingService';
import type { TopAnchors, TopRecords } from '@/services/topRankingService';
import { colorThemes } from '@/store/color';

const props = defineProps({
    records: { type: Object as PropType<TopRecords>, required: true },
    anchors: { type: Object as PropType<TopAnchors>, required: true },
    nf: { type: Boolean, default: false },
});
const title = computed(() => (props.nf ? 'NF top' : 'top'));
const anchorLabel = computed(() => t(props.nf ? 'local.nfAnchor' : 'local.ordinaryAnchor'));
const tooltip = useTemplateRef<{ show: () => void; hide: () => void }>('tooltip');
const hovered = ref<{ kind: 'axis' | 'ring'; index: number } | null>(null);
const tooltipLines = computed(() => {
    if (hovered.value === null) return [];
    if (hovered.value.kind === 'axis') return tooltipText(hovered.value.index).split('\n');
    const name = rings.value[hovered.value.index]?.name;
    return name ? [name] : [];
});
const nodeSeconds = [100, 60, 55, 50, 45, 40, 35, 30, 25];
const rows = computed(() => topAxes.map(({ level, stat }) => {
    const field = topField(props.nf, level, stat);
    const anchor = props.anchors[field]?.value ?? 0;
    const value = topMean(props.records[field], stat);
    return { field, level, stat, name: `${t(`level.${level}`)} ${t(`prop.${topStatNames[stat]}`)}`, value, anchor, radius: topRadius(value, anchor, stat) };
}));
const playerMax = computed(() => Math.max(...rows.value.map((row) => row.radius)));
const nodes = computed(() => {
    const etAnchor = props.anchors[topField(props.nf, 'e', 't')]?.value ?? 0;
    if (etAnchor <= 0) return [];
    const all = nodeSeconds.map((seconds) => ({ seconds, value: etAnchor / (10 * seconds) }));
    const outerIndex = all.findIndex((node) => node.value > playerMax.value);
    return outerIndex < 0 ? all : all.slice(0, outerIndex + 1);
});
const scale = computed(() => Math.max(100, playerMax.value, nodes.value.at(-1)?.value ?? 0));
const axisEnds = topAxes.map((_, index) => coordinates(index, 150));
const labels = topAxes.map((_, index) => {
    const position = coordinates(index, 174);
    return { ...position, anchor: Math.abs(position.x - 240) < 1 ? 'middle' : position.x < 240 ? 'end' : 'start' };
});
const playerPoints = computed(() => rows.value.map((row, index) => pointText(index, row.radius)).join(' '));
const anchorPoints = computed(() => rows.value.map((row, index) => pointText(index, row.anchor > 0 ? 100 : 0)).join(' '));
const rings = computed(() => nodes.value.map((node, index) => {
    const inner = nodes.value[index - 1]?.value ?? 0;
    const points = topAxes.map((_, axis) => pointText(axis, node.value)).join(' ');
    const innerPoints = topAxes.map((_, axis) => pointText(axis, inner)).join(' ');
    const middle = (inner + node.value) / 2;
    const etAnchor = props.anchors[topField(props.nf, 'e', 't')]?.value ?? 0;
    const grade = topGrade(middle, props.anchors, 100, props.nf);
    return {
        seconds: node.seconds,
        name: grade === null ? '--' : t(`ranking.grade.names.${grade.index}`),
        points,
        // Even-odd paths keep each tier band separate instead of stacking fills.
        path: `M ${points} Z M ${innerPoints} Z`,
        color: colorThemes.grade.value.getColor(etAnchor / (10 * middle)),
    };
}));

function coordinates(index: number, radius: number) {
    const angle = -Math.PI / 2 + index * 2 * Math.PI / topAxes.length;
    return { x: 240 + Math.cos(angle) * radius, y: 220 + Math.sin(angle) * radius };
}

function point(index: number, value: number) {
    return coordinates(index, value / scale.value * 150);
}

function pointText(index: number, value: number) {
    const { x, y } = point(index, value);
    return `${x},${y}`;
}

function formatGrade(radius: number) {
    const grade = topGrade(radius, props.anchors, 100, props.nf);
    return grade === null ? '--' : t('ranking.grade.format', { name: t(`ranking.grade.names.${grade.index}`), stage: (grade.position * 10).toFixed(1) });
}

function tooltipText(index: number) {
    const row = rows.value[index];
    return [
        formatGrade(row.radius),
        `${t('local.personal')}: ${formatTopValue(row.value, row.level, row.stat)}`,
        `${anchorLabel.value}: ${formatTopValue(row.anchor, row.level, row.stat)}`,
    ].join('\n');
}

function updateTooltip(event: MouseEvent) {
    const { target } = event;
    let next: typeof hovered.value = null;
    if (target instanceof SVGElement) {
        if (target.dataset.axis !== undefined) next = { kind: 'axis', index: Number(target.dataset.axis) };
        else if (target.dataset.ring !== undefined) next = { kind: 'ring', index: Number(target.dataset.ring) };
    }
    if (next?.kind !== hovered.value?.kind || next?.index !== hovered.value?.index) hovered.value = next;
}

watch(tooltipLines, (lines) => {
    if (lines.length) tooltip.value?.show();
    else tooltip.value?.hide();
}, { flush: 'post' });

const i18nMessages = {
    'zh-cn': { local: {
        personal: '玩家',
        ordinaryAnchor: 'Top 锚点',
        nfAnchor: 'NF Top 锚点',
    } },
    en: { local: {
        personal: 'Player',
        ordinaryAnchor: 'Top anchor',
        nfAnchor: 'NF Top anchor',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.top-radar {
    min-width: 0;
    width: 100%;
    margin: 0;
}
.top-radar-svg {
    display: block;
    width: 100%;
    height: auto;
    aspect-ratio: 480 / 440;
}
.top-radar-decoration {
    pointer-events: none;
}
.top-radar-grid {
    fill: none;
    stroke: var(--ui-border-color);
    stroke-width: 1;
}
.top-radar-axis {
    stroke: var(--ui-text-color-placeholder);
    stroke-width: 1;
}
.top-radar-anchor {
    fill: none;
    stroke-width: 2;
    stroke-dasharray: 4 4;
}
.top-radar-player {
    fill: var(--ui-color-success);
    fill-opacity: 0.12;
    stroke: var(--ui-color-success);
    stroke-width: 2;
}
.top-radar-point {
    fill: var(--ui-color-success);
}
.top-radar-label {
    fill: var(--ui-text-color-primary);
    font-size: 12px;
}
.top-radar-hit {
    stroke: transparent;
    stroke-width: 14;
    pointer-events: stroke;
    vector-effect: non-scaling-stroke;
}
.top-radar-hit:hover,
.top-radar-hit:focus-visible {
    stroke: var(--ui-color-primary-light-7);
    outline: none;
}
.top-radar-mark {
    fill: var(--ui-text-color-primary);
    font-size: 72px;
    font-weight: 700;
    opacity: 0.16;
    pointer-events: none;
}
.top-radar-tooltip {
    text-align: start;
    font-size: var(--ui-font-size-small);
}
</style>
