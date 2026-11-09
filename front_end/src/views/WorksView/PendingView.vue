<template>
    <MediaListPanel ref="panel" source="pending" show-status />
</template>

<script setup lang="ts">
import { useTemplateRef } from 'vue';

import MediaListPanel from '@/components/media/MediaListPanel.vue';

const panel = useTemplateRef<{ refresh: () => Promise<void> }>('panel');
defineExpose({ refresh: () => panel.value?.refresh() });
</script>
