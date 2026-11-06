<template>
    <label class="ms-stat-select">
        <span v-if="props.label !== ''">{{ props.label }}:</span>
        <select v-model="value" class="base-select base-select--small" :aria-label="props.label || t('prop.metric')" v-bind="$attrs" @change="handleChange">
            <option v-for="stat in options" :key="stat" :value="stat">{{ t(`prop.${stat}`) }}</option>
        </select>
    </label>
</template>

<script setup lang="ts">
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

const emit = defineEmits<{
    change: [value: string];
}>();

defineOptions({ inheritAttrs: false });

const value = defineModel({
    type: String,
    default: '',
});

const { t } = useI18n();

function handleChange(event: Event) {
    if (event.target instanceof HTMLSelectElement) emit('change', event.target.value);
}
</script>

<style scoped>
.ms-stat-select {
    display: inline-flex;
    flex: 1 1 8em;
    align-items: center;
    gap: 0.25em;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    font-size: var(--ui-font-size-extra-small);
}

.ms-stat-select > span {
    flex: none;
}

.ms-stat-select > select {
    flex: 1 1 0;
    width: 0;
}
</style>
