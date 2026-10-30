<template>
    <div :style="{ height, display: 'flex', alignItems: 'center' }">
        <BaseTooltip v-for="(item, index) in data" :key="item.name" :data-cy="item.name" :show-delay="200" :trigger="tooltip ? 'mouseenter focus' : 'manual'" :style="{ width: `${(item.value / sumValue * 100)}%`, height: '100%', background: item.color, borderTopLeftRadius: index === 0 ? '0.1em' : '0', borderBottomLeftRadius: index === 0 ? '0.1em' : '0', borderTopRightRadius: index === props.data.length - 1 ? '0.1em' : '0', borderBottomRightRadius: index === props.data.length - 1 ? '0.1em' : '0'}" @mouseenter="emit('itemEnter', index)" @mouseleave="emit('itemLeave')">
            <template #content>
                <span class="text-regular">
                    {{ item.name }}: {{ (item.value / sumValue * 100).toFixed(0) }}%({{ formatValue(item.value) }})
                </span>
            </template>
        </BaseTooltip>
    </div>
    <div v-if="legend">
        <span v-for="item in data" :key="item.name" style="margin: 0 0.2em">
            <template v-if="item.value > 0">
                <span class="dot" :style="{ background: item.color }" />
                <span class="text-regular">
                    {{ item.name }}: {{ (item.value / sumValue * 100).toFixed(0) }}%({{ formatValue(item.value) }})
                </span>
            </template>
        </span>
    </div>
</template>

<script setup lang="ts">
import { sum } from 'd3-array';
import { computed } from 'vue';
import type { PropType } from 'vue';

import BaseTooltip from '@/components/common/BaseTooltip.vue';

interface DataItem {
    name: string;
    value: number;
    color: string;
}

const props = defineProps({
    data: {
        type: Array<DataItem>,
        default: () => [],
    },
    legend: { type: Boolean, default: false },
    tooltip: { type: Boolean, default: true },
    height: { type: String, default: '0.3em' },
    formatValue: { type: Function as PropType<(value: number) => string>, default: (value: number) => String(value) },
});

const emit = defineEmits<{ itemEnter: [index: number]; itemLeave: [] }>();
const sumValue = computed(() => sum(props.data, (item) => item.value) || 1);
</script>

<style lang="less" scoped>
.dot {
    width: 0.75em;
    height: 0.75em;
    border-radius: 50%;
    display: inline-block;
    vertical-align: middle;
}
</style>
