<template>
    <div class="layout-row">
        <UserArbiterCSV :id="user.id" />
        <BaseButton v-if="isOwnProfile" :type="showCsvImport ? 'primary' : 'default'" :aria-expanded="showCsvImport" :aria-controls="csvPanelId" data-cy="toggle-arbiter-csv" @click="showCsvImport = !showCsvImport">
            {{ t('local.importCsv') }}
        </BaseButton>
        <span style="flex: 1" />
        <BaseButton size="small" :loading="loading" data-cy="refresh-videos" @click="refresh">
            {{ t('common.action.refresh') }}
        </BaseButton>
        <BaseButton v-if="presentation === 'table'" class="square-button" :type="showSetting ? 'primary' : 'default'" :aria-label="t('local.columns')" :aria-pressed="showSetting" @click="showSetting = !showSetting">
            <BaseIconSetting />
        </BaseButton>
    </div>
    <ArbiterCsvImport v-if="isOwnProfile && showCsvImport" :id="csvPanelId" :enabled="valid && !loading" :reading="csvReading" :has-csv="hasCsv" :filename="csvFilename" :count="localVideos.length" :issues="csvIssues" :failure="csvFailure" @import="importFile" @clear="clearCsv" />
    <p v-if="loading" role="status">
        {{ t('local.loading') }}
    </p>
    <p v-else-if="failed" role="alert">
        {{ t('local.failed') }}
    </p>
    <template v-else-if="valid">
        <div class="video-controls">
            <label>{{ t('local.overview') }}
                <select v-model="overview" data-cy="video-overview">
                    <option value="none">{{ t('local.none') }}</option>
                    <option value="calendar">{{ t('local.calendar') }}</option>
                    <option value="bv">{{ t('local.bv') }}</option>
                </select>
            </label>
        </div>
        <ActivityCalendarAbstract v-if="overview === 'calendar'" :video-list="displayVideos" :options="activityCalendarConfig" selectable :selected-date-key="selection.kind === 'date' ? selection.dateKey : undefined" @select-date="selectDate" />
        <BaseCardNormal v-else-if="overview === 'bv'" data-cy="video-bv-overview">
            <BBBvSummaryHeader />
            <ElScrollbar aria-orientation="horizontal" :style="{ zoom: BBBvSummaryConfig.zoom }">
                <BBBvSummary v-for="(level, index) in MS_Levels" :key="level" :level="level" :header="index === 0" :video-list="displayVideos" selectable :selected-b-v="selection.kind === 'bv' && selection.level === level ? selection.bv : undefined" @select-b-v="selectBV" />
            </ElScrollbar>
        </BaseCardNormal>
        <div class="video-controls" data-cy="video-range" aria-live="polite">
            <span>{{ rangeLabel }} · {{ t('local.count', { selected: selectedVideos.length, filtered: filteredVideos.length }) }}<span v-if="localVideos.length"> · {{ t('local.includesLocal') }}</span></span>
            <BaseButton v-if="selection.kind !== 'all'" size="small" text data-cy="clear-video-selection" @click="selection = { kind: 'all' }">
                {{ t('local.clear') }}
            </BaseButton>
        </div>
        <div class="video-controls" data-cy="video-shared-filters">
            <label>{{ t('local.presentation') }}
                <select v-model="presentation" data-cy="video-presentation">
                    <option value="table">{{ t('local.table') }}</option>
                    <option value="scatter">{{ t('local.scatter') }}</option>
                </select>
            </label>
            <SoftwareFilter v-model="filters.software" />
            <VideoStateFilter v-model="filters.state" :include-local="localVideos.length > 0" class="checkbox-buttons--compact" />
            <label>{{ t('common.prop.level') }}
                <select v-model="filters.level" data-cy="video-level-filter">
                    <option value="">{{ t('common.all') }}</option>
                    <option v-for="level in MS_Levels" :key="level" :value="level">{{ t(`common.level.${level}`) }}</option>
                    <option value="custom">{{ t('local.custom') }}</option>
                </select>
            </label>
            <ElSelect v-model="filters.mode" multiple collapse-tags clearable size="small" style="width: 10em" :placeholder="t('local.allModes')" :aria-label="t('common.prop.mode')">
                <ElOption v-for="mode in Object.values(MS_Mode)" :key="mode" :value="mode" :label="t(`common.mode.code${mode}`)" />
            </ElSelect>
        </div>
        <MultiSelector v-if="presentation === 'table' && showSetting" v-model="VideoListConfig.profile" :options="thisColumnChoices" :labels="thisColumnChoices.map((s) => t(`common.prop.${s}`))" />
        <VideoList
            v-if="presentation === 'table'"
            v-model:first="first" v-model:rows="rows" v-model:sort-field="sortField" v-model:sort-order="sortOrder"
            :videos="filteredVideos" :columns="VideoListConfig.profile" sortable paginator external-filtering
        >
            <template v-if="isOwnProfile" #rowActions="{ video, close }">
                <BaseButton text :disabled="!video.ongoing_tournament || revealing" data-cy="reveal-video" @click="requestReveal(video.id); close()">
                    <BaseIconShow />&nbsp;{{ t('local.reveal') }}
                </BaseButton>
            </template>
        </VideoList>
        <BaseCardNormal v-else>
            <VideoScatter :videos="filteredVideos" />
        </BaseCardNormal>
    </template>
    <ElDialog
        v-if="isOwnProfile" v-model="dialogVisible" :title="t('local.reveal')" append-to-body width="min(460px, 90vw)"
        :close-on-click-modal="!revealing" :close-on-press-escape="!revealing" :show-close="!revealing"
    >
        <p>{{ t('local.confirmReveal') }}</p>
        <template #footer>
            <BaseButton :disabled="revealing" @click="dialogVisible = false">
                {{ t('common.button.cancel') }}
            </BaseButton>
            <BaseButtonConfirm :loading="revealing" @click="confirmReveal" />
        </template>
    </ElDialog>
</template>

<script lang="ts" setup>
import '@/styles/layout.css';
// 个人主页的个人所有录像部分
import { ElDialog, ElOption, ElScrollbar, ElSelect } from 'element-plus';
import { computed, defineAsyncComponent, ref, useId, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import ArbiterCsvImport from './ArbiterCsvImport.vue';
import { useArbiterCsvDiff } from './useArbiterCsvDiff';
import { useProfileVideos } from './useProfileVideos';
import { createProfileVideoFilters, filterProfileVideos, selectProfileVideos } from './videoSelection';
import type { VideoSelection } from './videoSelection';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';
import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { BaseIconSetting, BaseIconShow } from '@/components/common/icon';
import SoftwareFilter from '@/components/Filters/SoftwareFilter.vue';
import VideoStateFilter from '@/components/Filters/VideoStateFilter.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import VideoList from '@/components/VideoList/App.vue';
import MultiSelector from '@/components/widgets/MultiSelector.vue';
import UserArbiterCSV from '@/components/widgets/UserArbiterCSV.vue';
import { revealUserVideo } from '@/services/userService';
import { activityCalendarConfig, BBBvSummaryConfig, store, VideoListConfig } from '@/store';
import { ArrayUtils } from '@/utils/arrays';
import { LoginStatus } from '@/utils/common/structInterface';
import { ColumnChoices, MS_Levels, MS_Mode } from '@/utils/ms_const';
import type { MS_Level } from '@/utils/ms_const';
import { UserProfile } from '@/utils/userprofile';

const user = defineModel('user', { type: UserProfile, required: true });

const ActivityCalendarAbstract = defineAsyncComponent(() => import('@/components/visualization/ActivityCalendarAbstract/App.vue'));
const BBBvSummary = defineAsyncComponent(() => import('@/components/visualization/BBBvSummary/App.vue'));
const BBBvSummaryHeader = defineAsyncComponent(() => import('@/components/visualization/BBBvSummary/Header.vue'));
const VideoScatter = defineAsyncComponent(() => import('@/components/visualization/VideoScatter/App.vue'));
const { videos, valid, loading, failed, viewerKey, refresh } = useProfileVideos(user);
const isOwnProfile = computed(() => store.login_status === LoginStatus.IsLogin && store.user.id === user.value.id);
const showCsvImport = ref(false);
const csvPanelId = useId();
const csvIdentity = computed(() => `${user.value.id}:${viewerKey.value}`);
const { localVideos, issues: csvIssues, failure: csvFailure, reading: csvReading, filename: csvFilename, hasCsv, importFile, clear: clearCsv } = useArbiterCsvDiff(videos, valid, csvIdentity, isOwnProfile);
const displayVideos = computed(() => [...videos.value, ...localVideos.value]);
const overview = ref<'none' | 'calendar' | 'bv'>('none');
const presentation = ref<'table' | 'scatter'>('table');
const selection = ref<VideoSelection>({ kind: 'all' });
const filters = ref(createProfileVideoFilters());
const first = ref(0);
const rows = ref(25);
const sortField = ref('upload_time');
const sortOrder = ref<number | undefined>(-1);
const selectedVideos = computed(() => selectProfileVideos(displayVideos.value, selection.value, activityCalendarConfig.value.useEndTime));
const filteredVideos = computed(() => filterProfileVideos(selectedVideos.value, filters.value));
const rangeLabel = computed(() => {
    const current = selection.value;
    if (current.kind === 'date') return current.dateKey;
    if (current.kind === 'bv') return `${t(`common.level.${current.level}`)} · BV ${current.bv}`;
    return t('local.allVideos');
});
function selectDate(dateKey: string) {
    selection.value = selection.value.kind === 'date' && selection.value.dateKey === dateKey ? { kind: 'all' } : { kind: 'date', dateKey };
}
function selectBV(value: { level: MS_Level; bv: number }) {
    const current = selection.value;
    selection.value = current.kind === 'bv' && current.level === value.level && current.bv === value.bv ? { kind: 'all' } : { kind: 'bv', ...value };
}
watch(overview, () => {
    selection.value = { kind: 'all' };
});
watch(() => activityCalendarConfig.value.useEndTime, () => {
    if (selection.value.kind === 'date') selection.value = { kind: 'all' };
});
watch([selection, filters], () => {
    first.value = 0;
}, { deep: true });
watch(displayVideos, () => {
    if (!valid.value) return;
    if (selection.value.kind === 'bv' && selectedVideos.value.length === 0) selection.value = { kind: 'all' };
    if (first.value >= filteredVideos.value.length) first.value = 0;
});
watch([() => user.value.id, viewerKey], () => {
    showCsvImport.value = false;
    selection.value = { kind: 'all' };
    filters.value = createProfileVideoFilters();
    overview.value = 'none';
    presentation.value = 'table';
    first.value = 0;
});

const showSetting = ref(false);
const thisColumnChoices = ArrayUtils.sortByReferenceOrder(['bv', 'bvs', 'stnb', 'ces', 'cls', 'corr', 'end_time', 'ioe', 'level', 'state', 'software', 'thrp', 'time', 'upload_time', 'path', 'pluck', 'file_size', 'mode'], ColumnChoices);

const dialogVisible = ref(false);
const selectedVideoId = ref<number>();
const revealing = ref(false);

function requestReveal(videoId: number) {
    selectedVideoId.value = videoId;
    dialogVisible.value = true;
}

async function confirmReveal() {
    if (!isOwnProfile.value || revealing.value || selectedVideoId.value === undefined) return;
    const videoId = selectedVideoId.value;
    const owner = user.value;
    revealing.value = true;
    try {
        await revealUserVideo(videoId);
        const video = owner.videos?.find((item) => item.id === videoId);
        if (video) video.ongoing_tournament = false;
        dialogVisible.value = false;
        actionSuccessNotification();
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        revealing.value = false;
    }
}

watch([() => user.value.id, viewerKey], () => {
    dialogVisible.value = false;
    selectedVideoId.value = undefined;
});

const i18nMessages = {
    'zh-cn': { local: {
        columns: '选择显示列',
        importCsv: '导入CSV',
        loading: '正在加载录像…',
        failed: '录像加载失败，请点击刷新重试。',
        overview: '概览',
        none: '不显示',
        calendar: '日历图',
        bv: 'BV 表',
        presentation: '展示',
        table: '表格',
        scatter: '散点图',
        allVideos: '全部录像',
        includesLocal: '含本地记录',
        allModes: '全部模式',
        custom: '自定义',
        clear: '清除选择',
        count: '范围内 {selected} 个录像，筛选后 {filtered} 个',
        reveal: '公开录像',
        confirmReveal: '公开后所有人都能观看此录像，且无法重新隐藏。录像仍计入其参加的所有比赛。确定公开吗？',
    } },
    en: { local: {
        columns: 'Select columns',
        importCsv: 'Import CSV',
        loading: 'Loading videos…',
        failed: 'Could not load videos. Refresh to retry.',
        overview: 'Overview',
        none: 'None',
        calendar: 'Calendar',
        bv: 'BV grid',
        presentation: 'Display',
        table: 'Table',
        scatter: 'Scatter plot',
        allVideos: 'All videos',
        includesLocal: 'Includes local records',
        allModes: 'All modes',
        custom: 'Custom',
        clear: 'Clear selection',
        count: '{selected} videos in range, {filtered} after filtering',
        reveal: 'Reveal video',
        confirmReveal: 'Everyone will be able to watch this video, and it cannot be hidden again. It will still count in all its tournaments. Reveal it?',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    margin: 0.5rem 0;
}
.video-controls label {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}
.video-controls select {
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    border: 1px solid var(--ui-border-color);
    padding: 0.2rem;
}
</style>
