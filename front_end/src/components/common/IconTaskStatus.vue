<template>
    <span v-if="status == 'loading'" class="text-primary">
        <i class="pi pi-spin pi-spinner-dotted" />
    </span>
    <span v-else-if="status == 'success'" class="text-success">
        <i class="pi pi-check-circle" />
    </span>
    <span v-else-if="status == 'error'" class="text-danger">
        <i class="pi pi-times-circle" />
    </span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

import 'primeicons/primeicons.css';
import type { TaskStatus } from '@/utils/common/structInterface';

defineProps({
    status: {
        type: String as PropType<TaskStatus>,
        default: '',
    },
});
</script>
