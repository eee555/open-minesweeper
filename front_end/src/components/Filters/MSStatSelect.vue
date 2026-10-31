<template>
    <ElSelect ref="selectRef" v-model="value" size="small" :append-to="appendTo" :popper-options="popperOptions">
        <template #label="{ label }">
            <span v-if="props.label !== ''">{{ props.label }}: </span>
            <span>{{ label }}</span>
        </template>
        <ElOption v-for="stat in options" :key="stat" :value="stat" :label="t(`prop.${stat}`)" />
    </ElSelect>
</template>

<script setup lang="ts">
import { useEventListener } from '@vueuse/core';
import { ElOption, ElSelect } from 'element-plus';
import type { Options } from 'element-plus';
import { computed, shallowRef, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
    label: {
        type: String,
        default: '',
    },
    options: {
        type: Array<string>,
        default: ['time', 'bv'],
    },
});

const { t } = useI18n();

const value = defineModel({
    type: String,
    default: '',
});

const selectRef = useTemplateRef<InstanceType<typeof ElSelect>>('selectRef');

// document.fullscreenElement 不是响应式的，需要自己监听 fullscreenchange。
const fullscreenElement = shallowRef<Element | null>(document.fullscreenElement);
useEventListener(document, 'fullscreenchange', () => {
    fullscreenElement.value = document.fullscreenElement;
});

// 全屏时浮层必须挂进全屏元素子树，否则浏览器不会绘制；非全屏保持默认挂 body。
const appendTo = computed<HTMLElement | undefined>(() => {
    const fullscreenEl = fullscreenElement.value;
    const selectEl = selectRef.value?.$el as Element | null | undefined;
    if (fullscreenEl === null || selectEl === null || selectEl === undefined) return undefined;
    return fullscreenEl.contains(selectEl) ? fullscreenEl as HTMLElement : undefined;
});

// 全屏元素是 position: fixed，祖先容器塌缩，Popper 会误判下方空间不足把面板翻到右侧，
// 因此全屏时只以 viewport 作为裁剪边界。
const popperOptions = computed<Partial<Options> | undefined>(() => {
    if (appendTo.value === undefined) return undefined;
    // Popper 的 boundary 只接受 'clippingParents' 或元素数组；清空后裁剪范围只剩 rootBoundary。
    const viewportBoundary = { boundary: [], rootBoundary: 'viewport' };
    return {
        modifiers: [
            {
                name: 'flip',
                options: { ...viewportBoundary, fallbackPlacements: ['bottom-start', 'top-start'] },
            },
            { name: 'preventOverflow', options: viewportBoundary },
        ],
    };
});
</script>
