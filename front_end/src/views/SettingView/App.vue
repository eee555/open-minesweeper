<template>
    <div class="layout-stack">
        <Appearance />
        <PlayerBadgeSettings />
        <Visualization />
        <MiniGame />
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

const i18nMessages = {
    'zh-cn': { local: {
        localCache: '本地缓存',
    } },
    en: { local: {
        localCache: 'Local Cache',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
