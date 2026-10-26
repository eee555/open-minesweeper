<template>
    <Tippy ref="tippy" v-bind="placed" :delay="[showDelay, hideDelay]" :duration="[showAnimation, hideAnimation]" :follow-cursor="followCursor" :interactive="interactive" :interactive-border="interactiveBorder" :trigger="trigger" :on-show="beforeShow" placement="auto-start">
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
import { computed, useTemplateRef } from 'vue';
import type { PropType } from 'vue';
import { Tippy } from 'vue-tippy';
import type { TippyComponent } from 'vue-tippy';

const props = defineProps({
    showDelay: { type: Number, default: 0 },
    hideDelay: { type: Number, default: 0 },
    showAnimation: { type: Number, default: 300 },
    hideAnimation: { type: Number, default: 250 },
    followCursor: { type: Boolean, default: false },
    interactive: { type: Boolean, default: false },
    interactiveBorder: { type: Number, default: 2 },
    trigger: { type: String, default: 'mouseenter focus' },
    // 不用 onShow 作 prop 名，避免和 Vue 的 onXxx 侦听器约定撞车。
    beforeShow: { type: Function as PropType<() => false | undefined>, default: undefined },
    // 表格会裁切或错位内部弹出层。需要浮在页面上时传入 document.body。
    appendTo: { type: Function as PropType<() => Element>, default: undefined },
});

const placed = computed(() => (props.appendTo ? { appendTo: props.appendTo } : {}));

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
