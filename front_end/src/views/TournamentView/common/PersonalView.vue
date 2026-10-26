<template>
    <ElTabs>
        <ElTabPane :label="t('local.summary')" lazy>
            <slot name="personalSummary" :videos="videos" :participant="participant" />
        </ElTabPane>
        <ElTabPane :label="t('local.videos')" lazy>
            <MultiSelector v-model="VideoListConfig.tournament" :options="thisColumnChoices" :labels="thisColumnChoices.map((s) => t(`prop.${s}`))" />
            <VideoList :videos="videos" :columns="VideoListConfig.tournament" sortable paginator />
        </ElTabPane>
    </ElTabs>
</template>

<script setup lang="ts" generic="TParticipant extends TournamentParticipant">
import { ElTabPane, ElTabs } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { httpErrorNotification } from '@/components/Notifications';
import VideoList from '@/components/VideoList/App.vue';
import MultiSelector from '@/components/widgets/MultiSelector.vue';
import { fetchParticipantVideos } from '@/services/tournamentService';
import { VideoListConfig } from '@/store';
import { ArrayUtils } from '@/utils/arrays';
import { ColumnChoices } from '@/utils/ms_const';
import type { TournamentParticipant } from '@/utils/tournaments';
import { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({ refreshDisabled: { type: Boolean, default: false } });
const emit = defineEmits<{ loading: [value: boolean, participantId: number] }>();
const participant = defineModel<TParticipant>({ required: true });
const loading = ref(false);

defineSlots<{
    personalSummary?: (props: { videos: VideoAbstract[]; participant: TParticipant }) => unknown;
}>();

const thisColumnChoices = ArrayUtils.sortByReferenceOrder(['upload_time', 'software', 'level', 'mode', 'time', 'bv', 'bvs', 'stnb', 'ioe', 'thrp', 'path', 'file_size'], ColumnChoices);
const videos = computed(() => participant.value.videos ?? []);

async function refresh() {
    if (props.refreshDisabled || loading.value || !participant.value.user_id || !participant.value.tournament_id) return;
    const owner = participant.value;
    loading.value = true;
    emit('loading', true, owner.id);
    try {
        const data = await fetchParticipantVideos({ userId: owner.user_id, tournamentId: owner.tournament_id });
        owner.videos = data.map((video) => new VideoAbstract(video));
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        loading.value = false;
        emit('loading', false, owner.id);
    }
}

watch([() => participant.value.id, () => props.refreshDisabled], () => {
    if (participant.value.videos === undefined) void refresh();
}, { immediate: true });
defineExpose({ refresh });

const i18nMessages = {
    'zh-cn': { local: {
        summary: '概览',
        videos: '录像',
    } },
    en: { local: {
        summary: 'Summary',
        videos: 'Videos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
