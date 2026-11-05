<template>
    <ElTabs model-value="all">
        <NewsQueue category="all" />
    </ElTabs>
</template>

<script setup lang="ts">
import { ElTabs } from 'element-plus';

import NewsQueue from './NewsQueue.vue';
</script>
