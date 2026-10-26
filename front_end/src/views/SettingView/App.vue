<template>
    <div style="display: flex; flex-direction: column; gap: 1rem;">
        <Appearance />
        <PlayerBadgeSettings />
        <section class="card">
            <h2 class="card-title">
                {{ t('local.thirdPartyTrust') }}
            </h2>
            <label class="checkbox">
                <input v-model="videoPlayerConfig.strangeDustTrust" class="checkbox-input" type="checkbox">
                <span>https://strange-dust.github.io/minesweeper-replay-analyzer/</span>
            </label>
        </section>
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
import { ElInputNumber } from 'element-plus';
import { useI18n } from 'vue-i18n';

import Appearance from './Appearance.vue';
import IDB from './IDB.vue';
import MiniGame from './MiniGame.vue';
import PlayerBadgeSettings from './PlayerBadge.vue';
import Visualization from './Visualization.vue';

import { vExperimental } from '@/components/ExperimentalFeature';
import { videoPlayerConfig } from '@/store';
import { STNB_const } from '@/utils/ms_const';

const i18nMessages = {
    'zh-cn': { local: {
        localCache: '本地缓存',
        stnbConst: 'STNB常数',
        thirdPartyTrust: '第三方网站信任列表',
    } },
    en: { local: {
        localCache: 'Local Cache',
        stnbConst: 'STNB Constants',
        thirdPartyTrust: 'Third Party Trust List',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
