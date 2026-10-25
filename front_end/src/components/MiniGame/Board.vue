<template>
    <div
        ref="surface" class="minigame-board" role="group" tabindex="-1" :aria-label="label" :aria-disabled="disabled"
        data-cy="minigame-board" @contextmenu.prevent @dragstart.prevent
        @pointerdown="pointerDown" @lostpointercapture="touchCancel"
    >
        <MinesweeperBoard :board="displayBoard" :size="size" :cursor-position="displayCursor">
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
        <div v-if="highlight !== null" class="minigame-board-highlight" :style="{ left: `${(transposed ? highlight.row : highlight.column) * size}px`, top: `${(transposed ? highlight.column : highlight.row) * size}px`, width: `${size}px`, height: `${size}px` }" aria-hidden="true" data-cy="minigame-board-highlight" />
    </div>
</template>

<script setup lang="ts">
import '@putianyi888/vue3-minesweeper-board/style.css';

import { BoardBackground, BoardForeground, MinesweeperBoard } from '@putianyi888/vue3-minesweeper-board';
import { useEventListener } from '@vueuse/core';
import { transpose } from 'd3-array';
import { computed, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';

import { ClassicMouseAutomaton } from '@/utils/classicMouse';
import type { ClassicMouseAction, ClassicMouseEvent } from '@/utils/classicMouse';
import { pressedBackground } from '@/utils/minigame/boardPress';
import type { BoardPress } from '@/utils/minigame/boardPress';
import type { TrainingMouseInput } from '@/utils/minigame/replay';
import type { TouchAction, TrainingTouchInput } from '@/utils/minigame/touchRecording';
import { scrollTouchAncestors, SingleTouchScroll } from '@/utils/minigame/touchScroll';

const props = defineProps({
    board: { type: Array as PropType<number[][]>, required: true },
    size: { type: Number, required: true },
    disabled: { type: Boolean, default: false },
    foregroundOpacity: { type: Number, default: 1 },
    minePressed: { type: Boolean, default: false },
    label: { type: String, required: true },
    highlight: { type: Object as PropType<{ row: number; column: number } | null>, default: null },
    cursorPosition: { type: Object as PropType<{ rowIndex: number; columnIndex: number } | undefined>, default: undefined },
    replayPress: { type: Object as PropType<BoardPress | null>, default: null },
    recordMouse: { type: Boolean, default: false },
    input: { type: String as PropType<'classic' | 'mouse' | 'touch'>, default: 'classic' },
    recordTouch: { type: Boolean, default: false },
    transposed: { type: Boolean, default: false },
});
const emit = defineEmits<{ action: [action: ClassicMouseAction, row: number, column: number, now: number]; record: [input: TrainingMouseInput]; touchRecord: [input: TrainingTouchInput] }>();
defineSlots<{ overlay?: () => unknown }>();
const surface = useTemplateRef<HTMLDivElement>('surface');
const mouse = new ClassicMouseAutomaton();
const pressed = shallowRef<BoardPress | null>(null);
let heldButtons = 0;
let touchId: number | null = null;
let lastPosition: { row: number; column: number } | null = null;
let suppressMouse = false;
const contacts = shallowRef(new Map<number, { row: number; column: number }>());
const touchScroll = new SingleTouchScroll();
const displayBoard = computed(() => (props.transposed ? transpose(props.board) : props.board));
const displayCursor = computed(() => (props.transposed && props.cursorPosition !== undefined ? { rowIndex: props.cursorPosition.columnIndex, columnIndex: props.cursorPosition.rowIndex } : props.cursorPosition));

const background = computed(() => {
    const press = props.input === 'touch' ? null : props.disabled ? props.replayPress : pressed.value;
    const value = pressedBackground(props.board, press, props.minePressed);
    return props.transposed && value !== undefined ? transpose(value) : value;
});

function coordinates(event: MouseEvent | PointerEvent) {
    const rect = surface.value?.getBoundingClientRect();
    if (rect === undefined || rect.width === 0 || rect.height === 0) return null;
    const row = (event.clientY - rect.top) / rect.height * displayBoard.value.length;
    const column = (event.clientX - rect.left) / rect.width * (displayBoard.value[0]?.length ?? 0);
    return props.transposed ? { row: column, column: row } : { row, column };
}

function cellAt(event: MouseEvent | PointerEvent) {
    const element = surface.value;
    if (element === null) return null;
    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0 || event.clientX < rect.left || event.clientY < rect.top || event.clientX >= rect.right || event.clientY >= rect.bottom) return null;
    // 也检查实际命中的元素，避免滚动容器裁剪之外的格子接受操作。
    if (!element.contains(document.elementFromPoint(event.clientX, event.clientY))) return null;
    const position = coordinates(event);
    return position === null ? null : { row: Math.floor(position.row), column: Math.floor(position.column) };
}

function step(event: ClassicMouseEvent, position: MouseEvent | PointerEvent) {
    const now = performance.now();
    const action = mouse.step(event);
    const cell = cellAt(position);
    pressed.value = cell !== null && (mouse.state === 'left-down' || mouse.state === 'both-down') ? { ...cell, chord: mouse.state === 'both-down' } : null;
    if (props.recordMouse && surface.value !== null) {
        const point = coordinates(position);
        if (point !== null) {
            lastPosition = point;
            emit('record', { ...lastPosition, now, action: event, cellSize: props.size });
        }
    }
    if (action !== null && cell !== null) emit('action', action, cell.row, cell.column, now);
}

function resetInput() {
    mouse.reset();
    heldButtons = 0;
    pressed.value = null;
    if (props.recordMouse && lastPosition !== null) emit('record', { ...lastPosition, now: performance.now(), action: null, cellSize: props.size });
    const id = touchId;
    touchId = null;
    if (id !== null && surface.value?.hasPointerCapture(id) === true) surface.value.releasePointerCapture(id);
    const previous = contacts.value;
    contacts.value = new Map();
    for (const [pointerId, position] of previous) {
        if (props.recordTouch) emit('touchRecord', { ...position, pointerId, action: 'cancel', now: performance.now(), cellSize: props.size });
        if (surface.value?.hasPointerCapture(pointerId) === true) surface.value.releasePointerCapture(pointerId);
    }
}

function reset() {
    touchScroll.reset();
    resetInput();
}

// 使用 mouse 事件接收每个键的变化；鼠标的 pointerdown/up 仅报告首键按下和末键弹起。
useEventListener(window, 'mousedown', (event) => {
    if (props.disabled || props.input === 'touch' || suppressMouse || touchId !== null || (event.button !== 0 && event.button !== 2)) return;
    const mask = event.button === 0 ? 1 : 2;
    if (heldButtons === 0 && (cellAt(event) === null || (event.buttons & 3) !== mask)) return;
    if (heldButtons === 0) surface.value?.focus({ preventScroll: true });
    event.preventDefault();
    heldButtons |= mask;
    step(event.button === 0 ? 'lc' : 'rc', event);
});
useEventListener(window, 'mouseup', (event) => {
    if (props.disabled || props.input === 'touch' || suppressMouse || touchId !== null || (event.button !== 0 && event.button !== 2)) return;
    const mask = event.button === 0 ? 1 : 2;
    if ((heldButtons & mask) === 0) return;
    heldButtons &= ~mask;
    step(event.button === 0 ? 'lr' : 'rr', event);
});
useEventListener(window, 'mousemove', (event) => {
    if (props.disabled || props.input === 'touch' || suppressMouse || touchId !== null) return;
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

// Native panning would cancel the pointer stream and cannot be disabled midway
// when a second finger lands. Keep capture and scroll ancestors ourselves.
useEventListener(window, 'pointerdown', (event) => {
    if (props.input !== 'touch' || event.pointerType !== 'touch') return;
    touchScroll.down(event.pointerId, event.clientX, event.clientY, event.target instanceof Node && surface.value?.contains(event.target) === true);
}, { capture: true });

function pointerDown(event: PointerEvent) {
    if (event.pointerType === 'mouse') {
        suppressMouse = false;
        return;
    }
    event.preventDefault(); // 阻止兼容 mouse 事件造成重复操作。
    suppressMouse = true;
    if (props.disabled) return;
    if (props.input === 'mouse') {
        reset();
        return;
    }
    if (props.input === 'touch') {
        if (event.pointerType !== 'touch' || contacts.value.has(event.pointerId)) return;
        const cell = cellAt(event);
        if (cell === null) return;
        surface.value?.focus({ preventScroll: true });
        surface.value?.setPointerCapture(event.pointerId);
        const now = recordContact(event, 'down');
        emit('action', 'left', cell.row, cell.column, now);
        return;
    }
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
    suppressMouse = event.pointerType !== 'mouse';
    if (props.input === 'touch' && event.pointerType === 'touch' && surface.value !== null) {
        const movement = touchScroll.move(event.pointerId, event.clientX, event.clientY);
        if (movement !== null) scrollTouchAncestors(surface.value, movement.x, movement.y);
    }
    // Resolve board coordinates after scrolling so traces stay aligned.
    if (contacts.value.has(event.pointerId)) recordContact(event, 'move');
    if (event.pointerId === touchId) step('mv', event);
});

function touchUp(event: PointerEvent) {
    touchScroll.up(event.pointerId);
    if (event.pointerType === 'mouse') suppressMouse = false;
    if (contacts.value.has(event.pointerId)) {
        recordContact(event, 'up');
        if (surface.value?.hasPointerCapture(event.pointerId) === true) surface.value.releasePointerCapture(event.pointerId);
        return;
    }
    if (event.pointerId !== touchId) return;
    step('lr', event);
    reset();
}

function touchCancel(event: PointerEvent) {
    if (event.type !== 'lostpointercapture') touchScroll.up(event.pointerId);
    if (contacts.value.has(event.pointerId)) {
        recordContact(event, 'cancel');
        return;
    }
    if (event.pointerType === 'mouse' || event.pointerId === touchId) reset();
}

function recordContact(event: PointerEvent, action: TouchAction): number {
    const position = action === 'cancel' ? contacts.value.get(event.pointerId) : coordinates(event) ?? contacts.value.get(event.pointerId);
    const now = performance.now();
    if (position === undefined || position === null) return now;
    const updated = new Map(contacts.value);
    if (action === 'up' || action === 'cancel') updated.delete(event.pointerId);
    else updated.set(event.pointerId, position);
    contacts.value = updated;
    if (props.recordTouch) emit('touchRecord', { ...position, now, action, pointerId: event.pointerId, cellSize: props.size });
    return now;
}

useEventListener(window, 'pointerup', touchUp);
useEventListener(window, 'pointercancel', touchCancel);
// Ending a game or resizing cancels gameplay presses, but a held finger may
// continue scrolling. Losing capture during that cleanup is not a finger lift.
watch(() => [props.disabled, props.size], resetInput);
watch(() => props.input, reset);
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
