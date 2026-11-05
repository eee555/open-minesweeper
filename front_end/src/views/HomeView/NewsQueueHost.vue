<template>
    <ElTabs model-value="all">
        <NewsQueue category="all" />
    </ElTabs>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus-tabs.less';
import { ElTabs } from 'element-plus';

import NewsQueue from './NewsQueue.vue';
</script>
