<template>
    <ElTabs model-value="news">
        <NewsQueue />
    </ElTabs>
</template>

<script setup lang="ts">
import { ElTabs } from 'element-plus';

import NewsQueue from './NewsQueue.vue';
</script>
