<template>
    <div class="home-content">
        <div class="home-top-row">
            <ElTabs class="home-news-tabs" type="border-card">
                <NewsQueue />
            </ElTabs>
            <NormalTournamentQueue />
        </div>
        <ElTabs v-model="active_tab" type="border-card" style="margin-top: 2%;">
            <NewestQueue :is-active="active_tab === 'newest'" />
            <ReviewQueue />
        </ElTabs>
    </div>
</template>

<script setup lang='ts'>
import { ElTabs } from 'element-plus';
import { ref } from 'vue';

import NewestQueue from './NewestQueue.vue';
import NewsQueue from './NewsQueue.vue';
import NormalTournamentQueue from './NormalTournamentQueue.vue';
import ReviewQueue from './ReviewQueue.vue';

const active_tab = ref('newest');
</script>

<style lang='less'>
.home-content {
    box-sizing: border-box;
    container-type: inline-size;
    min-width: 0;
    overflow: auto;
    padding: 1%;
}

.bottom_tabs {
    overflow: auto;
}

.aside-tip-title {
    font-size: 14px;
    display: flex;
    align-items: center;
    margin-top: 5%;
}

.text-button:hover {
    cursor: pointer;
}

.home-top-row {
    align-items: stretch;
    display: grid;
    gap: 2%;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
}

.home-news-tabs {
    min-height: 300px;
    min-width: 0;
}

@container (max-width: 900px) {
    .home-top-row {
        grid-template-columns: 1fr;
    }
}
</style>
