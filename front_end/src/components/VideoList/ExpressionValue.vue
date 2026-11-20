<template>
    <span v-if="result.bool !== undefined" :class="result.bool ? 'text-success' : 'text-danger'" :title="result.text" :aria-label="result.text" role="img">
        <BaseIconTick v-if="result.bool" aria-hidden="true" /><BaseIconClose v-else aria-hidden="true" />
    </span>
    <span v-else class="text" :title="result.error || undefined">{{ result.text }}</span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';

import type { VideoColumnResult } from './columns';

import { BaseIconClose, BaseIconTick } from '@/components/common/icon';

defineProps({ result: { type: Object as PropType<VideoColumnResult>, required: true } });
</script>
