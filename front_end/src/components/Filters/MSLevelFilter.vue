<template>
    <div class="checkbox-buttons" role="group" :aria-label="t('prop.level')">
        <label v-for="l in MS_Levels" :key="l" class="checkbox-button">
            <input v-model="level" class="checkbox-button-input" type="checkbox" :value="l" @change="handleChange">
            <span class="checkbox-button-content">{{ t(`level.${l}`) }}</span>
        </label>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import type { MS_Level } from '@/utils/ms_const';
import { MS_Levels } from '@/utils/ms_const';

const emit = defineEmits<{ change: [value: MS_Level[]] }>();

const { t } = useI18n();

const level = defineModel<MS_Level[]>({
    type: Array as PropType<MS_Level[]>,
    default: () => [...MS_Levels],
});

async function handleChange() {
    await nextTick();
    emit('change', level.value);
}
</script>
