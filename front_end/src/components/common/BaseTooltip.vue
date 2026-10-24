<template>
    <Tippy ref="tippy" :delay="[showDelay, hideDelay]" :duration="[showAnimation, hideAnimation]" :follow-cursor="followCursor" :trigger="trigger" :on-show="beforeShow" placement="auto-start">
        <slot />
        <template #content>
            <div class="card card-small">
                <slot name="content" />
            </div>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import { useTemplateRef } from 'vue';
import { Tippy } from 'vue-tippy';
import type { TippyComponent } from 'vue-tippy';

defineProps({
    showDelay: { type: Number, default: 0 },
    hideDelay: { type: Number, default: 0 },
    showAnimation: { type: Number, default: 300 },
    hideAnimation: { type: Number, default: 250 },
    followCursor: { type: Boolean, default: false },
    trigger: { type: String, default: 'mouseenter focus' },
    // 不用 onShow 作 prop 名，避免和 Vue 的 onXxx 侦听器约定撞车。
    beforeShow: { type: Function, default: undefined },
});

const tippy = useTemplateRef<TippyComponent>('tippy');
defineExpose({
    show: () => tippy.value?.show(),
    hide: () => tippy.value?.hide(),
});

defineSlots<{
    default?: () => unknown;
    content?: () => unknown;
}>();
</script>
