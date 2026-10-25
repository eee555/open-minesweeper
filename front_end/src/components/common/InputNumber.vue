<template>
    <input
        v-bind="inputAttrs"
        :value="displayValue"
        type="number"
        :min="min" :max="max"
        class="base-input-number text text-small"
        :class="externalClass"
        @blur="commitValue" @change="commitValue"
        @input="handleInput" @keydown.enter="commitValue"
    >
</template>

<script setup lang="ts">
import '@/styles/text.css';

import { computed, ref, useAttrs, watch } from 'vue';

import { clamp } from '@/utils/math';

const props = defineProps({
    min: { type: Number, default: -Infinity },
    max: { type: Number, default: Infinity },
    integer: { type: Boolean, default: false },
});

defineOptions({ inheritAttrs: false });

const model = defineModel<number>({ required: true });

const attrs = useAttrs();
const displayValue = ref(String(model.value));
const externalClass = computed(() => attrs.class);
const inputAttrs = computed(() => {
    const restAttrs = { ...attrs };
    delete restAttrs.class;
    return restAttrs;
});

function parseInput(value: string) {
    if (value.trim() === '') return null;

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function handleInput(event: Event) {
    const target = event.target as HTMLInputElement;
    const parsed = parseInput(target.value);

    displayValue.value = target.value;
    if (parsed !== null && (!props.integer || Number.isInteger(parsed)) && parsed >= props.min && parsed <= props.max) {
        model.value = parsed;
    }
}

function commitValue() {
    const parsed = parseInput(displayValue.value);
    const value = parsed ?? model.value;
    const nextValue = clamp(props.integer ? Math.round(value) : value, props.min, props.max);

    model.value = nextValue;
    displayValue.value = String(nextValue);
}

watch(model, (value) => {
    displayValue.value = String(clamp(value, props.min, props.max));
});
</script>

<style scoped lang="less">
.base-input-number {
    appearance: textfield;
    box-sizing: border-box;
    height: 24px;
    min-width: 0;
    padding: 1px 8px;
    color: var(--ui-input-text-color, var(--ui-text-color-regular));
    line-height: 22px;
    background-color: var(--ui-input-bg-color, var(--ui-fill-color-blank));
    border: 1px solid var(--ui-input-border-color, var(--ui-border-color));
    border-radius: var(--ui-input-border-radius, var(--ui-border-radius-base));
    outline: none;
    transition: var(--ui-transition-box-shadow), border-color var(--ui-transition-duration);

    &::placeholder {
        color: var(--ui-input-placeholder-color, var(--ui-text-color-placeholder));
    }

    &:hover {
        border-color: var(--ui-input-hover-border-color, var(--ui-border-color-hover));
    }

    &:focus {
        border-color: var(--ui-input-focus-border-color, var(--ui-color-primary));
        box-shadow: 0 0 0 1px var(--ui-input-focus-border-color, var(--ui-color-primary)) inset;
    }

    &:disabled {
        color: var(--ui-disabled-text-color);
        cursor: not-allowed;
        background-color: var(--ui-disabled-bg-color);
        border-color: var(--ui-disabled-border-color);
    }

    &::-webkit-outer-spin-button,
    &::-webkit-inner-spin-button {
        appearance: none;
        margin: 0;
    }
}
</style>
