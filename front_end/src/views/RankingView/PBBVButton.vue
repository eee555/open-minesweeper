<template>
    <Tippy interactive trigger="click" placement="bottom-start" max-width="none" role="dialog" :append-to="appendToBody">
        <template #default="{ state }">
            <BaseButton :type="active ? 'primary' : 'default'" :aria-pressed="active" aria-haspopup="dialog" :aria-expanded="state.isVisible" :data-level="level" class="pb-level-button">
                {{ t(`level.${level}`) }}<span v-if="active">{{ selectedBv }}</span>
                <i class="pi pi-angle-down" aria-hidden="true" />
            </BaseButton>
        </template>
        <template #content="{ hide }">
            <div class="pb-bv-grid" :data-level="level" role="group" :aria-label="`${t(`level.${level}`)} 3BV`" @keydown.esc.stop="hide">
                <div class="pb-bv-columns pb-bv-header">
                    <span aria-hidden="true" />
                    <span v-for="digit in digits" :key="digit">{{ digit }}</span>
                </div>
                <div class="pb-bv-body">
                    <div v-for="row in rows" :key="row.tens" class="pb-bv-columns pb-bv-row" :data-tens="row.tens">
                        <span class="pb-bv-label">{{ row.tens }}</span>
                        <template v-for="cell in row.cells" :key="cell.bv">
                            <BaseButton v-if="cell.valid" size="small" :disabled="cell.count === 0" :type="active && selectedBv === cell.bv ? 'primary' : 'default'" :aria-pressed="active && selectedBv === cell.bv" :data-bv="cell.bv" :aria-label="`${cell.bv} 3BV (${cell.count})`" :title="`${cell.bv} 3BV`" @click="emit('select', cell.bv); hide()">
                                {{ cell.count }}
                            </BaseButton>
                            <span v-else aria-hidden="true" />
                        </template>
                    </div>
                </div>
            </div>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';

import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';
import { pbBVLimits } from '@/services/pbRankingService';
import type { PBCounts } from '@/services/pbRankingService';
import type { MS_Level } from '@/utils/ms_const';

const props = defineProps({
    level: { type: String as PropType<MS_Level>, required: true },
    selectedLevel: { type: String as PropType<MS_Level>, required: true },
    selectedBv: { type: Number, required: true },
    nf: { type: Boolean, required: true },
    counts: { type: Object as PropType<PBCounts>, required: true },
});
const emit = defineEmits<{ select: [bv: number] }>();
const { t } = useI18n();
const appendToBody = () => document.body;
const digits = Array.from({ length: 10 }, (_, digit) => digit);
const active = computed(() => props.level === props.selectedLevel);
const rows = computed(() => {
    const { min, max } = pbBVLimits[props.level];
    return Array.from({ length: Math.floor(max / 10) + 1 }, (_, tens) => ({
        tens,
        cells: digits.map((digit) => {
            const value = tens * 10 + digit;
            return { bv: value, valid: value >= min && value <= max, count: props.counts[`${props.nf ? 'nf' : 'std'}:${props.level}:${value}`] ?? 0 };
        }),
    })).filter((row) => row.cells.some((cell) => cell.valid && cell.count > 0));
});
</script>

<style scoped>
.pb-level-button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.pb-bv-grid {
    box-sizing: border-box;
    width: 28rem;
    max-width: calc(100vw - 24px);
    padding: 4px;
    background: var(--ui-bg-color-overlay);
    color: var(--ui-text-color-primary);
    border: 1px solid var(--ui-border-color);
}

.pb-bv-columns {
    display: grid;
    grid-template-columns: 2rem repeat(10, minmax(0, 1fr));
    gap: 2px;
    align-items: center;
}

.pb-bv-header {
    text-align: center;
    min-height: 24px;
    border-bottom: 1px solid var(--ui-border-color);
}

.pb-bv-header,
.pb-bv-body {
    overflow-y: auto;
    scrollbar-gutter: stable;
}

.pb-bv-body {
    max-height: min(60vh, 28rem);
}

.pb-bv-row {
    margin-top: 2px;
}

.pb-bv-label {
    text-align: center;
    font-variant-numeric: tabular-nums;
}

.pb-bv-grid .base-button {
    min-width: 0;
    min-height: 28px;
    margin: 0;
    padding: 1px;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
}
</style>
