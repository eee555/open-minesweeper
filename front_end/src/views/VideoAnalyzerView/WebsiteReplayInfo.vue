<template>
    <section class="text text-small website-replay-info" :aria-label="t('local.website')" :aria-busy="loading">
        <div class="website-replay-info__details">
            <div class="website-replay-info__identity website-replay-info__row">
                <span class="website-replay-info__id">{{ t('local.videoId') }} #{{ id }}</span>
                <time v-if="info" class="website-replay-info__upload-time" :datetime="info.video.upload_time" :title="t('prop.upload_time')">{{ utc_to_local_format(info.video.upload_time) }}</time>
                <span v-else>--</span>
            </div>
            <div class="website-replay-info__player website-replay-info__row">
                <PlayerName v-if="info" :user-id="info.video.player" />
                <span v-else>--</span>
                <span v-if="info && info.tournament_ids.length > 0" class="website-replay-info__tournaments">
                    {{ t('tournament.tournament') }}
                    <RouterLink v-for="tournamentId in info.tournament_ids" :key="tournamentId" class="link" :to="`/tournament/${tournamentId}`">#{{ tournamentId }}</RouterLink>
                </span>
            </div>
            <div class="website-replay-info__rankings website-replay-info__row">
                <span v-if="errorMessage" role="alert" class="text-danger">{{ t('local.loadFailed') }}: {{ errorMessage }}</span>
                <span v-else-if="loading">{{ t('local.loading') }}</span>
                <template v-else-if="info && info.rankings.length > 0">
                    <span v-for="(ranking, index) in info.rankings" :key="index">{{ rankingLabel(ranking) }} #{{ ranking.rank }}</span>
                </template>
                <span v-else>{{ info ? t('local.unranked') : '--' }}</span>
            </div>
            <div class="website-replay-info__filename website-replay-info__row" :title="info?.filename">
                {{ info?.filename ?? '--' }}
            </div>
        </div>
        <nav class="website-replay-info__links" :aria-label="t('local.links')">
            <a class="base-button base-button--size-small website-replay-info__link website-replay-info__replay-download" :href="replayDownloadUrl" :download="info?.filename ?? ''" :title="t('local.downloadReplay')" :aria-label="t('local.downloadReplay')">
                <i class="pi pi-file-export" aria-hidden="true" />
            </a>
            <a class="base-button base-button--size-small website-replay-info__link website-replay-info__strange-dust" :href="strangeDustUrl || undefined" role="link" aria-label="StrangeDust Analyzer" title="StrangeDust Analyzer" :aria-disabled="strangeDustUrl ? undefined : true" :tabindex="strangeDustUrl ? undefined : -1" target="_blank" rel="noopener noreferrer">
                <img :src="strangeDustIcon" alt="" width="16" height="16">
            </a>
            <a class="base-button base-button--size-small website-replay-info__link website-replay-info__offline-download" :href="offlineDownloadUrl" :download="offlineDownloadFilename" :title="t('local.downloadOffline')" :aria-label="t('local.downloadOffline')">
                <img :src="analyzerIcon" alt="" width="16" height="16">
            </a>
        </nav>
    </section>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import '@/styles/text.css';
import '@/styles/button.css';
import 'primeicons/primeicons.css';
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import analyzerVersion from '../../../local-analyzer/version.json';

import type { SiteReplayInfo, SiteReplayRanking } from './useSiteReplayInfo';

import strangeDustIcon from '@/assets/strange-dust.ico';
import analyzerIcon from '@/assets/video-analyzer.svg';
import PlayerName from '@/components/PlayerName.vue';
import type { MS_Software } from '@/utils/ms_const';
import { getReplayDownloadUrl, getReplayPreviewUrl, getStrangeDustAnalyzerUrl } from '@/utils/replayLinks';
import { utc_to_local_format } from '@/utils/system/tools';

const props = defineProps({
    id: { type: String, required: true },
    info: { type: Object as PropType<SiteReplayInfo | null>, default: null },
    loading: { type: Boolean, default: false },
    errorMessage: { type: String, default: '' },
    software: { type: String as PropType<MS_Software | null>, default: null },
});
const strangeDustUrl = computed(() => (props.software === null ? '' : getStrangeDustAnalyzerUrl(getReplayPreviewUrl(props.id, props.software))));
const replayDownloadUrl = computed(() => getReplayDownloadUrl(props.id));
const offlineDownloadFilename = `OpenMinesweeperVideoAnalyzer-${analyzerVersion.version}.zip`;
const offlineDownloadUrl = `${import.meta.env.BASE_URL}assets/${offlineDownloadFilename}`;

function rankingLabel(ranking: SiteReplayRanking): string {
    const label = ranking.ranking === 'saolei'
        ? t(ranking.stat.endsWith('t') ? 'local.saoleiTime' : 'local.saoleiBvs')
        : t(ranking.ranking === 'pb' ? 'local.pb' : 'local.pluck');
    return ranking.nf ? `${label} (${t('nf')})` : label;
}

const i18nMessages = {
    'zh-cn': { local: {
        website: '站内录像信息',
        links: '录像分析链接',
        downloadReplay: '下载录像文件',
        downloadOffline: '下载离线包',
        videoId: '录像 ID',
        loading: '正在加载网站信息…',
        loadFailed: '网站信息加载失败',
        unranked: '未入榜',
        saoleiTime: '扫雷榜时间',
        saoleiBvs: '扫雷榜速度',
        pb: '3BV 榜',
        pluck: 'pluck 榜',
    } },
    en: { local: {
        website: 'Website replay information',
        links: 'Replay analysis links',
        downloadReplay: 'Download replay file',
        downloadOffline: 'Download offline package',
        videoId: 'Replay ID',
        loading: 'Loading website information…',
        loadFailed: 'Website information failed to load',
        unranked: 'Not ranked',
        saoleiTime: 'Saolei time',
        saoleiBvs: 'Saolei speed',
        pb: '3BV ranking',
        pluck: 'pluck ranking',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.website-replay-info {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 8px;
    min-width: 0;
}
.website-replay-info__details {
    min-width: 0;
}
.website-replay-info__links {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    min-width: 0;
}
.website-replay-info__link {
    width: 28px;
    height: 28px;
    padding: 0;
    text-decoration: none;
}
.website-replay-info__link img {
    object-fit: contain;
}
.website-replay-info__link i {
    font-size: 16px;
}
.website-replay-info__link[href]:hover {
    border-color: var(--button-hover-border);
    background: var(--button-hover-background);
    color: var(--button-hover-color);
}
.website-replay-info__link[href]:active {
    background: var(--button-active-background);
}
.website-replay-info__link[aria-disabled='true'] {
    border-color: var(--button-disabled-border);
    background: var(--button-disabled-background);
    color: var(--button-disabled-color);
    cursor: not-allowed;
}
.website-replay-info__link[aria-disabled='true'] img {
    opacity: 0.5;
}
.website-replay-info__row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px 10px;
    min-height: 1.5em;
}
.website-replay-info__tournaments {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
}
.website-replay-info__filename {
    display: block;
    overflow-wrap: anywhere;
}
</style>
