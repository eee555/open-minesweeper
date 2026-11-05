<template>
    <ElTabs v-model="selectedTab" data-cy="all-participants-tabs">
        <ElTabPane :label="t('local.ranking')" lazy :name="rankingTabName">
            <slot name="allSummary" :data="result" :on-participant-select="handleAllSummaryRowClick" />
        </ElTabPane>
        <ElTabPane v-for="participant in viewedParticipants" :key="participant.id" lazy :name="participant.id">
            <template #label>
                <PlayerName v-if="participant.user_id !== 0" :user-id="participant.user_id" :interactive="false" />
                &nbsp;
                <BaseTextButton data-cy="all-participants-tab-close" underline="never" :aria-label="t('local.closeTab')" @keydown.stop @click.stop="handleAllSummaryTabClose(participant.id)">
                    <BaseIconClose style="scale: 65%" aria-hidden="true" />
                </BaseTextButton>
            </template>
            <PersonalView v-if="participant.user_id !== 0" :model-value="participant">
                <template #personalSummary="{ videos }">
                    <slot name="personalSummary" :videos="videos" :participant="participant" />
                </template>
            </PersonalView>
        </ElTabPane>
    </ElTabs>
</template>

<script setup lang="ts" generic="TParticipant extends TournamentParticipant">
import '@/styles/vendors/element-plus-tabs.less';
import { ElTabPane, ElTabs } from 'element-plus';
import { ref, shallowRef } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import PersonalView from './PersonalView.vue';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconClose } from '@/components/common/icon';
import PlayerName from '@/components/PlayerName.vue';
import type { TournamentParticipant } from '@/utils/tournaments';
import type { VideoAbstract } from '@/utils/videoabstract';

defineProps({
    result: { type: Array as PropType<TParticipant[]>, default: () => [] },
});

defineSlots<{
    allSummary: (props: { data: TParticipant[]; onParticipantSelect: (row: TParticipant) => void }) => unknown;
    personalSummary: (props: { videos: VideoAbstract[]; participant: TParticipant }) => unknown;
}>();

const rankingTabName = -1;
const selectedTab = ref(rankingTabName);
const viewedParticipants = shallowRef<TParticipant[]>([]);

function handleAllSummaryRowClick(row: TParticipant) {
    if (row.user_id === 0) return;
    const index = viewedParticipants.value.findIndex((item) => item.id === row.id);
    if (index === -1) {
        viewedParticipants.value = [...viewedParticipants.value, row];
    }
    selectedTab.value = row.id;
}

function handleAllSummaryTabClose(participantId: number) {
    viewedParticipants.value = viewedParticipants.value.filter((participant) => participant.id !== participantId);
    if (selectedTab.value === participantId) {
        selectedTab.value = rankingTabName;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        ranking: '排名',
        closeTab: '关闭选手页签',
    } },
    en: { local: {
        ranking: 'Ranking',
        closeTab: 'Close participant tab',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
