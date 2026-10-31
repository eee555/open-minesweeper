<template>
    <div class="layout-stack">
        <Appearance />
        <PlayerBadgeSettings />
        <Visualization />
        <MiniGame />
        <section v-experimental class="card">
            <h2 class="card-title">
                {{ t('local.stnbConst') }}
            </h2>
            <div class="description-layout">
                <dl class="descriptions">
                    <div class="description-item">
                        <dt>{{ t('level.b') }}</dt>
                        <dd>
                            <ElInputNumber v-model="STNB_const.b" size="small" :controls="false" />
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('level.i') }}</dt>
                        <dd>
                            <ElInputNumber v-model="STNB_const.i" size="small" :controls="false" />
                        </dd>
                    </div>
                    <div class="description-item">
                        <dt>{{ t('level.e') }}</dt>
                        <dd>
                            <ElInputNumber v-model="STNB_const.e" size="small" :controls="false" />
                        </dd>
                    </div>
                </dl>
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
import '@/styles/descriptions.css';
import '@/styles/cards.css';
import '@/styles/layout.css';
import { ElInputNumber } from 'element-plus';
import { useI18n } from 'vue-i18n';

import Appearance from './Appearance.vue';
import IDB from './IDB.vue';
import MiniGame from './MiniGame.vue';
import PlayerBadgeSettings from './PlayerBadge.vue';
import Visualization from './Visualization.vue';

import { vExperimental } from '@/components/ExperimentalFeature';
import { STNB_const } from '@/utils/ms_const';

const i18nMessages = {
    'zh-cn': { local: {
        localCache: '本地缓存',
        stnbConst: 'STNB常数',
    } },
    en: { local: {
        localCache: 'Local Cache',
        stnbConst: 'STNB Constants',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
