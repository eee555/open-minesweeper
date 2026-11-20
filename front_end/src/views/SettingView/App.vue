<template>
    <div class="layout-stack">
        <Appearance />
        <PlayerBadgeSettings />
        <Visualization />
        <MiniGame />
        <section class="card" data-cy="fixed-player-columns-settings">
            <h2 class="card-title">
                {{ t('local.playerColumns') }}
            </h2>
            <ColumnsEditor v-model="playerColumns" scope="fixed-player" :storage-error="playerColumnsError" />
            <p class="text-secondary text-small">
                {{ t('local.preview') }}
            </p>
            <VideoList :videos="previewVideos" :columns="playerColumns" display-only :previewable="false" data-cy="fixed-player-columns-preview" />
        </section>
        <section class="card" data-cy="mixed-players-columns-settings">
            <h2 class="card-title">
                {{ t('local.mixedColumns') }}
            </h2>
            <ColumnsEditor v-model="mixedColumns" scope="mixed-players" :storage-error="mixedColumnsError" />
            <p class="text-secondary text-small">
                {{ t('local.preview') }}
            </p>
            <VideoList :videos="previewVideos" :columns="mixedColumns" display-only :previewable="false" data-cy="mixed-players-columns-preview" />
        </section>
        <section class="card" data-cy="video-tooltip-settings">
            <h2 class="card-title">
                {{ t('local.videoTooltip') }}
            </h2>
            <ColumnsEditor v-model="descriptionColumns" description :storage-error="descriptionError" />
            <p class="text-secondary text-small">
                {{ t('local.preview') }}
            </p>
            <div data-cy="video-tooltip-preview">
                <VideoAbstractDisplay :video="videoColumnPreview" />
            </div>
        </section>
        <section class="card">
            <h2 class="card-title">
                {{ t('local.localCache') }}
            </h2>
            <IDB />
        </section>
    </div>
</template>

<script lang="ts" setup name="UserSettings">
import '@/styles/cards.css';
import '@/styles/layout.css';
import { useI18n } from 'vue-i18n';

import Appearance from './Appearance.vue';
import IDB from './IDB.vue';
import MiniGame from './MiniGame.vue';
import PlayerBadgeSettings from './PlayerBadge.vue';
import Visualization from './Visualization.vue';

import VideoList from '@/components/VideoList/App.vue';
import ColumnsEditor from '@/components/VideoList/ColumnsEditor.vue';
import { videoColumnStore, videoDescriptionStore } from '@/components/VideoList/columnStore';
import { videoColumnPreview } from '@/components/VideoList/presets';
import VideoAbstractDisplay from '@/components/widgets/VideoAbstractDisplay.vue';

const { columns: playerColumns, error: playerColumnsError } = videoColumnStore('fixed-player');
const { columns: mixedColumns, error: mixedColumnsError } = videoColumnStore('mixed-players');
const { columns: descriptionColumns, error: descriptionError } = videoDescriptionStore;

const previewVideos = [videoColumnPreview];

const i18nMessages = {
    'zh-cn': { local: {
        playerColumns: '录像表格 - 个人主页和比赛个人页',
        mixedColumns: '录像表格 - 数据库检索和首页',
        videoTooltip: '录像提示信息',
        preview: '预览',
        localCache: '本地缓存',
    } },
    en: { local: {
        playerColumns: 'Replay table - Player profiles and tournaments',
        mixedColumns: 'Replay table - Database search and home',
        videoTooltip: 'Replay tooltip',
        preview: 'Preview',
        localCache: 'Local Cache',
    } },
    es: { local: {
        playerColumns: 'Tabla de repeticiones - Perfiles y torneos',
        mixedColumns: 'Tabla de repeticiones - Búsqueda e inicio',
        videoTooltip: 'Información de repetición',
        preview: 'Vista previa',
        localCache: 'Caché local',
        stnbConst: 'Constantes STNB',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
