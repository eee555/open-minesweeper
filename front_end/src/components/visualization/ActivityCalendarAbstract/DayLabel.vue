<template>
    <span
        class="text-regular"
        :style="{
            display: 'inline-block',
            fontSize: `${cellFullSize - 8}px`,
            lineHeight: `${cellFullSize}px`,
            marginTop: '0',
            marginRight: `${cellMargin}px`,
        }"
    >
        <IconSetting>
            <Setting />
        </IconSetting><br>
        Sun<br>Mon<br>Tue<br>Wed<br>Thu<br>Fri<br>Sat
    </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import Setting from './Setting.vue';

import IconSetting from '@/components/widgets/IconSetting.vue';

const props = defineProps({
    cellSize: { type: Number, default: 14 }, // 格子大小，单位为px
    cellMargin: { type: Number, default: 3 }, // 格子间距，单位为px
});

const cellFullSize = computed(() => props.cellSize + props.cellMargin);
</script>
