<template>
    <div
        ref="surface" class="minigame-board" role="group" tabindex="-1" :aria-label="label" :aria-disabled="disabled"
        data-cy="minigame-board" @contextmenu.prevent @dragstart.prevent
        @pointerdown="touchDown" @pointerup="touchUp" @pointercancel="touchCancel" @lostpointercapture="touchCancel"
    >
        <MinesweeperBoard :board="board" :size="size" :cursor-position="cursorPosition">
            <template #background>
                <BoardBackground class="minigame-board-background" :board="background" />
            </template>
            <template #foreground>
                <div class="minigame-board-layers">
                    <BoardForeground class="minigame-board-foreground" :style="{ opacity: foregroundOpacity }" />
                    <slot name="overlay" />
                </div>
            </template>
        </MinesweeperBoard>
        <div v-if="highlight !== null" class="minigame-board-highlight" :style="{ left: `${highlight.column * size}px`, top: `${highlight.row * size}px`, width: `${size}px`, height: `${size}px` }" aria-hidden="true" data-cy="minigame-board-highlight" />
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-minesweeper-board/style.css';

import { BoardBackground, BoardForeground, MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import { useEventListener } from '@vueuse/core';
import { computed, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';

import { ClassicMouseAutomaton } from '@/utils/classicMouse';
import type { ClassicMouseAction, ClassicMouseEvent } from '@/utils/classicMouse';
import { pressedBackground } from '@/utils/minigame/boardPress';
import type { BoardPress } from '@/utils/minigame/boardPress';
import type { TrainingMouseInput } from '@/utils/minigame/replay';

const props = defineProps({
    board: { type: Array as PropType<number[][]>, required: true },
    size: { type: Number, required: true },
    disabled: { type: Boolean, default: false },
    foregroundOpacity: { type: Number, default: 1 },
    label: { type: String, required: true },
    highlight: { type: Object as PropType<{ row: number; column: number } | null>, default: null },
    cursorPosition: { type: Object as PropType<{ rowIndex: number; columnIndex: number } | undefined>, default: undefined },
    replayPress: { type: Object as PropType<BoardPress | null>, default: null },
    recordMouse: { type: Boolean, default: false },
});
const emit = defineEmits<{ action: [action: ClassicMouseAction, row: number, column: number, now: number]; record: [input: TrainingMouseInput] }>();
defineSlots<{ overlay?: () => unknown }>();
const surface = useTemplateRef<HTMLDivElement>('surface');
const mouse = new ClassicMouseAutomaton();
const pressed = shallowRef<BoardPress | null>(null);
let heldButtons = 0;
let touchId: number | null = null;
let lastPosition: { row: number; column: number } | null = null;

const background = computed(() => pressedBackground(props.board, props.disabled ? props.replayPress : pressed.value));

function cellAt(event: MouseEvent | PointerEvent) {
    const element = surface.value;
    if (element === null) return null;
    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0 || event.clientX < rect.left || event.clientY < rect.top || event.clientX >= rect.right || event.clientY >= rect.bottom) return null;
    // 也检查实际命中的元素，避免滚动容器裁剪之外的格子接受操作。
    if (!element.contains(document.elementFromPoint(event.clientX, event.clientY))) return null;
    return {
        row: Math.floor((event.clientY - rect.top) / rect.height * props.board.length),
        column: Math.floor((event.clientX - rect.left) / rect.width * (props.board[0]?.length ?? 0)),
    };
}

function step(event: ClassicMouseEvent, position: MouseEvent | PointerEvent) {
    const now = performance.now();
    const action = mouse.step(event);
    const cell = cellAt(position);
    pressed.value = cell !== null && (mouse.state === 'left-down' || mouse.state === 'both-down') ? { ...cell, chord: mouse.state === 'both-down' } : null;
    if (props.recordMouse && surface.value !== null) {
        const rect = surface.value.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            lastPosition = { row: (position.clientY - rect.top) / rect.height * props.board.length, column: (position.clientX - rect.left) / rect.width * (props.board[0]?.length ?? 0) };
            emit('record', { ...lastPosition, now, action: event, cellSize: props.size });
        }
    }
    if (action !== null && cell !== null) emit('action', action, cell.row, cell.column, now);
}

function reset() {
    mouse.reset();
    heldButtons = 0;
    pressed.value = null;
    if (props.recordMouse && lastPosition !== null) emit('record', { ...lastPosition, now: performance.now(), action: null, cellSize: props.size });
    const id = touchId;
    touchId = null;
    if (id !== null && surface.value?.hasPointerCapture(id) === true) surface.value.releasePointerCapture(id);
}

// 使用 mouse 事件接收每个键的变化；鼠标的 pointerdown/up 仅报告首键按下和末键弹起。
useEventListener(window, 'mousedown', (event) => {
    if (props.disabled || touchId !== null || (event.button !== 0 && event.button !== 2)) return;
    const mask = event.button === 0 ? 1 : 2;
    if (heldButtons === 0 && (cellAt(event) === null || (event.buttons & 3) !== mask)) return;
    if (heldButtons === 0) surface.value?.focus({ preventScroll: true });
    event.preventDefault();
    heldButtons |= mask;
    step(event.button === 0 ? 'lc' : 'rc', event);
});
useEventListener(window, 'mouseup', (event) => {
    if (props.disabled || touchId !== null || (event.button !== 0 && event.button !== 2)) return;
    const mask = event.button === 0 ? 1 : 2;
    if ((heldButtons & mask) === 0) return;
    heldButtons &= ~mask;
    step(event.button === 0 ? 'lr' : 'rr', event);
});
useEventListener(window, 'mousemove', (event) => {
    if (props.disabled || touchId !== null) return;
    if (heldButtons === 0) {
        if (props.recordMouse) step('mv', event);
        return;
    }
    if ((event.buttons & 3) !== heldButtons) reset();
    else step('mv', event);
});
useEventListener(window, 'blur', reset);
useEventListener(document, 'visibilitychange', () => {
    if (document.hidden) reset();
});

function touchDown(event: PointerEvent) {
    if (event.pointerType === 'mouse') return;
    event.preventDefault(); // 阻止兼容 mouse 事件造成重复操作。
    if (props.disabled) return;
    if (touchId !== null || heldButtons !== 0 || !event.isPrimary) {
        reset();
        return;
    }
    if (cellAt(event) === null) return;
    surface.value?.focus({ preventScroll: true });
    touchId = event.pointerId;
    surface.value?.setPointerCapture(event.pointerId);
    step('lc', event);
}

useEventListener(window, 'pointermove', (event) => {
    if (event.pointerId === touchId) step('mv', event);
});

function touchUp(event: PointerEvent) {
    if (event.pointerId !== touchId) return;
    step('lr', event);
    reset();
}

function touchCancel(event: PointerEvent) {
    if (event.pointerType === 'mouse' || event.pointerId === touchId) reset();
}

watch(() => props.disabled, reset);
onBeforeUnmount(reset);
</script>

<style scoped>
.minigame-board {
    position: relative;
    width: max-content;
    line-height: 0;
    cursor: default;
    user-select: none;
    touch-action: none;
}

.minigame-board-highlight {
    position: absolute;
    pointer-events: none;
    box-shadow: inset 0 0 0 3px var(--ui-color-primary);
    background: color-mix(in srgb, var(--ui-color-primary) 25%, transparent);
}

.minigame-board-layers {
    display: grid;
}

.minigame-board-layers > :deep(*) {
    grid-area: 1 / 1;
}
</style>
