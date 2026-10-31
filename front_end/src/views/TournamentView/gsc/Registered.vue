<template>
    <div v-loading="loading" class="tag-list" data-cy="gsc-participants">
        <ElTag v-for="participant of participants" :key="participant.id">
            <PlayerName v-if="participant.user_id !== 0" :user-id="participant.user_id" />
            <span v-else>{{ t('anonymous') }}</span>
            <span v-if="participant.arbiter_identifier__identifier"> · {{ participant.arbiter_identifier__identifier }}</span>
        </ElTag>
    </div>
</template>

<script setup lang="ts">
import { ElTag, vLoading } from 'element-plus';
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';
import type { GSCParticipant } from '@/utils/gsc';

defineProps({
    participants: { type: Array<GSCParticipant>, required: true },
    loading: { type: Boolean, default: false },
});

const { t } = useI18n();
</script>

<style lang="less" scoped>
.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5em;
}

.el-tag {
    height: auto;
    padding-block: 0.25em;
    white-space: normal;
    overflow-wrap: anywhere;
}
</style>
