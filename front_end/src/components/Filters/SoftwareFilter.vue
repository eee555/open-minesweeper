<template>
    <div class="checkbox-buttons checkbox-buttons--compact" role="group" :aria-label="t('prop.software')">
        <label v-for="l in MS_Softwares" :key="l" class="checkbox-button">
            <input v-model="level" class="checkbox-button-input" type="checkbox" :value="l" :aria-label="t(`software.${l}`)" @change="handleChange">
            <span class="checkbox-button-content"><SoftwareIcon :software="l" /></span>
        </label>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import type { MS_Software } from '@/utils/ms_const';
import { MS_Softwares } from '@/utils/ms_const';

const emit = defineEmits<{ change: [value: MS_Software[]] }>();

const level = defineModel<MS_Software[]>({
    type: Array as PropType<MS_Software[]>,
    default: () => [...MS_Softwares],
});

const { t } = useI18n();

async function handleChange() {
    await nextTick();
    emit('change', level.value);
}
</script>
