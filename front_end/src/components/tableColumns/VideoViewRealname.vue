<template>
    <ElTableColumn v-slot="scope" :label="t('prop.realName')" width="auto">
        <span class="nobr">
            <PlayerName class="name" :user-id="scope.row.player__id" />
        </span>
    </ElTableColumn>
</template>

<script setup lang="ts">
import { ElTableColumn } from 'element-plus';
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';

const { t } = useI18n();
</script>

<style lang="less">
.nobr {
    white-space: nowrap;
    hyphens: none;
}
</style>
