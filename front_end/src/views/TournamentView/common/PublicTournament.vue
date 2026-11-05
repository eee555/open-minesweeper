<template>
    <Title :tournament="tournament" />
    <slot name="description" />
    <template v-if="state === TournamentState.Preparing || state === TournamentState.Ongoing">
        <h3 class="tournament-section-heading">
            {{ t('gsc.howToParticipate') }}
        </h3>
        <slot name="participationGuide" />
    </template>
    <section v-if="uploadParticipant" v-show="participant && state === TournamentState.Ongoing && autoUploaderEnabled" class="tournament-auto-upload">
        <h3 class="tournament-section-heading">
            {{ t('local.autoUpload') }}
            <a class="link text" :href="uploadGuideUrl" target="_blank" rel="noopener noreferrer">{{ t('local.uploadGuide') }}</a>
        </h3>
        <AutoUploader
            :participant="uploadParticipant" :filter="autoUploaderFilter" :enabled="!!participant && state === TournamentState.Ongoing && autoUploaderEnabled"
            :disabled="personalLoading" @busy="uploadBusy = $event"
        >
            <template #filter>
                <slot name="autoUploaderFilter" />
            </template>
        </AutoUploader>
    </section>
    <template v-if="state === TournamentState.Awarded || showLiveData || showPreparingParticipants">
        <h3 class="tournament-section-heading">
            {{ t('local.data') }}
            <DataExporter v-if="state === TournamentState.Awarded" :key="tournament.id" v-model="allVideos" lazy :fetch-data="getVideos">
                {{ t('local.export') }}
            </DataExporter>
        </h3>
        <AllParticipants v-if="state === TournamentState.Awarded" :key="tournament.id" v-loading="loading" :result="participants">
            <template #allSummary="slotProps">
                <slot name="allSummary" v-bind="slotProps" />
            </template>
            <template #personalSummary="slotProps">
                <slot name="personalSummary" v-bind="slotProps" />
            </template>
        </AllParticipants>
        <ElTabs v-else v-model="selectedTab" data-cy="tournament-data-tabs">
            <ElTabPane name="participants">
                <template #label>
                    <span>{{ t('local.participants') }}</span>
                    <BaseButton text :title="t('local.refreshParticipants')" :aria-label="t('local.refreshParticipants')" :disabled="loading" data-cy="participants-refresh" @keydown.stop @click.stop="refreshParticipants">
                        <BaseIconRefresh />
                    </BaseButton>
                </template>
                <slot name="allSummary" :data="participants" :on-participant-select="ignoreSelection" />
            </ElTabPane>
            <ElTabPane v-if="participant && showLiveData" name="personal">
                <template #label>
                    <span>{{ t('gsc.realTimeScore') }}</span>
                    <BaseButton text :title="t('local.refreshPersonal')" :aria-label="t('local.refreshPersonal')" :disabled="uploadBusy || personalLoading" data-cy="personal-score-refresh" @keydown.stop @click.stop="personalView?.refresh()">
                        <BaseIconRefresh />
                    </BaseButton>
                </template>
                <PersonalView :key="participant.id" ref="personalView" v-loading="personalLoading" :model-value="participant" :refresh-disabled="uploadBusy" @loading="setPersonalLoading">
                    <template #personalSummary="slotProps">
                        <slot name="personalSummary" v-bind="slotProps" />
                    </template>
                </PersonalView>
            </ElTabPane>
        </ElTabs>
    </template>
</template>

<script setup lang="ts" generic="TParticipant extends TournamentParticipant">
import '@/styles/vendors/element-plus-tabs.less';
import { ElTabPane, ElTabs, vLoading } from 'element-plus';
import { computed, ref, shallowRef, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import AllParticipants from './AllParticipants.vue';
import AutoUploader from './AutoUploader.vue';
import PersonalView from './PersonalView.vue';
import Title from './Title.vue';
import type { AutoUploadVideo } from './utils';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import DataExporter from '@/components/widgets/DataExporter.vue';
import { fetchTournamentVideos } from '@/services/tournamentService';
import { globalNow } from '@/utils/datetime';
import { getDocsUrl } from '@/utils/docs';
import { TournamentState, TournamentSubclass } from '@/utils/ms_const';
import type { Tournament, TournamentParticipant } from '@/utils/tournaments';
import type { VideoAbstract, VideoAbstractData } from '@/utils/videoabstract';

const props = defineProps({
    tournament: { type: Object as PropType<Tournament>, required: true },
    participants: { type: Array as PropType<TParticipant[]>, required: true },
    index: { type: Number, required: true },
    loading: { type: Boolean, default: false },
    refreshParticipants: { type: Function as PropType<() => Promise<void>>, required: true },
    autoUploaderEnabled: { type: Boolean, default: false },
    autoUploaderFilter: { type: Function as PropType<(video: AutoUploadVideo) => boolean>, required: true },
});
defineSlots<{
    description: () => unknown;
    participationGuide: () => unknown;
    autoUploaderFilter: () => unknown;
    allSummary: (props: { data: TParticipant[]; onParticipantSelect: (row: TParticipant) => void }) => unknown;
    personalSummary: (props: { videos: VideoAbstract[]; participant: TParticipant }) => unknown;
}>();
const state = computed(() => props.tournament.getDisplayState(globalNow.value));
const showLiveData = computed(() => state.value === TournamentState.Ongoing || state.value === TournamentState.Finished);
const showPreparingParticipants = computed(() => state.value === TournamentState.Preparing && props.tournament.subclass === TournamentSubclass.GSC);
const participant = computed<TParticipant | undefined>(() => props.participants[props.index]);
const uploadParticipant = shallowRef<TParticipant>();
const uploadBusy = ref(false);
const personalLoading = ref(false);
const personalView = useTemplateRef<{ refresh: () => Promise<void> }>('personalView');
const selectedTab = ref('participants');
const allVideos = ref<VideoAbstractData[]>([]);
watch(participant, (value) => {
    if (value) uploadParticipant.value = value;
    else selectedTab.value = 'participants';
}, { immediate: true });
watch(() => participant.value?.id, () => {
    personalLoading.value = false;
}, { flush: 'sync' });
watch(() => props.tournament.id, () => {
    allVideos.value = [];
});

async function getVideos() {
    const { id } = props.tournament;
    const videos = await fetchTournamentVideos(id);
    if (props.tournament.id === id) allVideos.value = videos;
    return videos;
}
function ignoreSelection() {
    // Other participants' replays remain private before awards.
}
function setPersonalLoading(value: boolean, id: number) {
    if (participant.value?.id === id) personalLoading.value = value;
}

const i18nMessages = {
    'zh-cn': { local: {
        autoUpload: '自动上传比赛录像',
        uploadGuide: '上传指南',
        data: '比赛数据',
        participants: '参赛者',
        export: '导出所有录像数据',
        refreshParticipants: '刷新参赛者',
        refreshPersonal: '刷新个人录像',
    } },
    en: { local: {
        autoUpload: 'Automatic replay upload',
        uploadGuide: 'Upload guide',
        data: 'Tournament data',
        participants: 'Participants',
        export: 'Export all video stats',
        refreshParticipants: 'Refresh participants',
        refreshPersonal: 'Refresh personal videos',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
const uploadGuideUrl = getDocsUrl('guide/tournament#auto-upload');
</script>

<style scoped>
@import '@/styles/link.css';

.tournament-section-heading {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    border-top: 1px solid var(--ui-border-color-light);
    padding-top: 0.75rem;
}

.tournament-section-heading > .link {
    font-weight: normal;
}
</style>
