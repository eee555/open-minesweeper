<template>
    <button class="stat-header" type="button" :aria-label="`${t(`level.${level}`)} ${label}`" :aria-pressed="selected === field" @click="emit('select', field)">
        {{ label }}
    </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { SaoleiStat } from '@/services/saoleiRankingService';
import type { SaoleiField, SaoleiLevel } from '@/services/saoleiRankingService';

const props = defineProps({
    level: { type: String as PropType<SaoleiLevel | 'sum'>, required: true },
    stat: { type: String as PropType<SaoleiStat>, required: true },
    selected: { type: String as PropType<SaoleiField>, required: true },
});

const emit = defineEmits<{ select: [field: SaoleiField] }>();

const { t } = useI18n();
const field = computed<SaoleiField>(() => `${props.level}${props.stat}`);
const label = computed(() => t(`prop.${SaoleiStat[props.stat]}`));
</script>

<style scoped>
.stat-header {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.4rem;
    width: 100%;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    padding: 0;
    cursor: pointer;
}

.stat-header[aria-pressed="true"] {
    color: var(--ui-color-primary);
}
</style>
