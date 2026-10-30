<template>
    <span class="text" :class="statusToClass[status]">
        {{ status }}
    </span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';

defineProps({
    status: { type: String as PropType<DjangoTaskResultStatus>, default: 'NULL' },
});

const statusToClass = {
    READY: 'text-primary',
    RUNNING: 'text-warning',
    SUCCESSFUL: 'text-success',
    FAILED: 'text-danger',
    NULL: 'text-info',
} as const;
</script>
