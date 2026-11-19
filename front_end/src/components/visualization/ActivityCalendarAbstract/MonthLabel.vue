<template>
    <span
        v-for="date of generateMonthLabelRange(startDate, endDate)" :key="date.toISOString()" class="text-regular" :style="{
            position: 'absolute',
            fontSize: '12px',
            top: 0,
            left: `${(date.getTime() - startWeekTime) / fullWeek * cellFullSize}px`,
            transform: 'translate(-50%,0)'
        }"
    >
        {{ monthFormat.format(date) }}
    </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { fullWeek, getWeekTime } from '@/utils/datetime';

const props = defineProps({
    startDate: { type: Date, required: true },
    endDate: { type: Date, required: true },
    cellSize: { type: Number, default: 14 }, // 格子大小，单位为px
    cellMargin: { type: Number, default: 3 }, // 格子间距，单位为px
});

const { locale } = useI18n();
const monthFormat = computed(() => new Intl.DateTimeFormat(locale.value === 'dev' ? 'en' : locale.value, { month: 'short' }));
const startWeekTime = computed(() => getWeekTime(props.startDate));
const cellFullSize = computed(() => props.cellSize + props.cellMargin);

function generateMonthLabelRange(startDate: Date, endDate: Date) {
    let currentDate = new Date(startDate);
    if (currentDate.getDate() > 15) {
        currentDate.setMonth(currentDate.getMonth() + 1);
        currentDate.setDate(15);
    }
    const monthLabels = [];
    while (currentDate <= endDate) {
        monthLabels.push(currentDate);
        currentDate = new Date(currentDate);
        currentDate.setMonth(currentDate.getMonth() + 1);
    }
    return monthLabels;
}
</script>
