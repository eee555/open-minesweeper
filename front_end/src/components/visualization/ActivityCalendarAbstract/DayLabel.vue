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
        <template v-for="(day, i) in weekdays" :key="i"><br v-if="i">{{ day }}</template>
    </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import Setting from './Setting.vue';

import IconSetting from '@/components/widgets/IconSetting.vue';

const props = defineProps({
    cellSize: { type: Number, default: 14 }, // 格子大小，单位为px
    cellMargin: { type: Number, default: 3 }, // 格子间距，单位为px
});

const { locale } = useI18n();
const weekdays = computed(() => {
    const format = new Intl.DateTimeFormat(locale.value === 'dev' ? 'en' : locale.value, { weekday: 'short', timeZone: 'UTC' });
    return Array.from({ length: 7 }, (_, day) => format.format(Date.UTC(2023, 0, day + 1)));
});
const cellFullSize = computed(() => props.cellSize + props.cellMargin);
</script>
