<template>
    <MasonryLayout class="server-statistics">
        <div data-statistic-item="disk">
            <DiskUsage :section="data?.diskusage" :loading="loading" :failed="failed" @refresh="refresh" />
        </div>
        <div data-statistic-item="process">
            <MemoryUsage :section="data?.memoryusage?.memory" :loading="loading" :failed="failed" @refresh="refresh" />
        </div>
        <div data-statistic-item="redis">
            <RedisMemoryUsage :section="data?.memoryusage?.redis" :loading="loading" :failed="failed" @refresh="refresh" />
        </div>
        <div data-statistic-item="tasks">
            <TaskSummary :section="data?.tasksummary" :loading="loading" :failed="failed" @refresh="refresh" />
        </div>
        <div data-statistic-item="videos">
            <VideoSummary :section="data?.videosummary" :loading="loading" :failed="failed" @refresh="refresh" />
        </div>
        <div data-statistic-item="top">
            <TopAnchors />
        </div>
    </MasonryLayout>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue';

import MemoryUsage from './MemoryUsage.vue';
import RedisMemoryUsage from './RedisMemoryUsage.vue';
import type { MonitorSnapshot } from './statistics';
import { useStatistic } from './useStatistic';

import MasonryLayout from '@/components/common/MasonryLayout.vue';

const DiskUsage = defineAsyncComponent(() => import('./DiskUsage.vue'));
const TaskSummary = defineAsyncComponent(() => import('./TaskSummary.vue'));
const VideoSummary = defineAsyncComponent(() => import('./VideoSummary.vue'));
const TopAnchors = defineAsyncComponent(() => import('./TopAnchors.vue'));

const { data, loading, failed, refresh } = useStatistic<MonitorSnapshot>('/api/monitor/summary');
</script>
