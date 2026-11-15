<template>
    <i class="pi" :class="iconClasses[props.state]" aria-hidden="true" />
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

import 'primeicons/primeicons.css';

type SortState = 'none' | 'ascending' | 'descending';

const props = defineProps({
    state: { type: String as PropType<SortState>, default: 'none' },
});

const iconClasses: Record<SortState, string> = {
    none: 'pi-sort-alt',
    ascending: 'pi-sort-amount-down-alt',
    descending: 'pi-sort-amount-down',
};
</script>
