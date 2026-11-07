<template>
    <div class="slider-demo-block">
        <div>
            <ElSlider v-model="range" range :min="props.min" :max="props.max" @change="$emit('change', range)" />
        </div>
        <div>
            <ElInputNumber
                v-model="range[0]" size="small" step-strictly :min="props.min" :max="range[1]"
                :value-on-clear="props.min" @change="$emit('change', range)"
            />
            {{ text }}
            <ElInputNumber
                v-model="range[1]" size="small" step-strictly :min="range[0]" :max="props.max"
                :value-on-clear="props.max" @change="$emit('change', range)"
            />
        </div>
    </div>
</template>

<script setup lang="ts" name="RangeSlider">
import '@/styles/vendors/element-plus-slider.css';

import { ElInputNumber, ElSlider } from 'element-plus';
import type { PropType } from 'vue';

const props = defineProps({
    min: {
        type: Number,
        default: 0,
    },
    max: {
        type: Number,
        default: 100,
    },
    text: {
        type: String,
        default: '',
    },
});

defineEmits(['change']);

const range = defineModel({ type: Array as PropType<number[]>, required: true });
</script>

<style scoped>
.slider-demo-block {
    width: 200px;
    align-content: center;
    display: inline-block;
}

.el-slider {
    height: 20px;
}

.el-input-number {
    margin: 0px;
    width: 90px;
    height: 20px;
}

.el-input-number:nth-child(1) {
    float: left;
}

.el-input-number:nth-child(2) {
    float: right;
}
</style>
