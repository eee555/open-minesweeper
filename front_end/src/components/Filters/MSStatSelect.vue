<template>
    <ElSelect v-model="value" size="small">
        <template #label="{ label }">
            <span v-if="props.label !== ''">{{ props.label }}: </span>
            <span>{{ label }}</span>
        </template>
        <ElOption v-for="stat in options" :key="stat" :value="stat" :label="t(`prop.${stat}`)" />
    </ElSelect>
</template>

<script setup lang="ts">
import { ElOption, ElSelect } from 'element-plus';
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
</script>
