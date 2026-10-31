<template>
    <BaseCardNormal>
        <div style="margin-bottom: 0.5em;">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('platform.w') }}&nbsp;#{{ id }}
                    </span>
                </template>
                <template #end>
                    <CarouselControl :ref-carousel="refCarousel!" :length="carouselLength" />
                </template>
            </PrToolbar>
        </div>
        <ElCarousel v-if="verified" ref="refCarousel" trigger="click" :autoplay="false" indicator-position="none" :loop="false" arrow="never">
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('prop.update_time')" :span="3">
                        {{ toISODateTimeString(info.update_time) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.trophy')" :span="3">
                        {{ info.trophy }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('prop.time')" :span="3">
                        {{ ms_to_s(info.b_t_ms) }} | {{ ms_to_s(info.i_t_ms) }} | {{ ms_to_s(info.e_t_ms) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('prop.ioe')" :span="3">
                        {{ maybeUndefinedToFixed(info.b_ioe, 2) }} | {{ maybeUndefinedToFixed(info.i_ioe, 2) }} | {{ maybeUndefinedToFixed(info.e_ioe, 2) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('prop.mastery')" :span="3">
                        {{ maybeUndefined(info.b_mastery) }} | {{ maybeUndefined(info.i_mastery) }} | {{ maybeUndefined(info.e_mastery) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('prop.winstreak')" :span="3">
                        {{ maybeUndefined(info.b_winstreak) }} | {{ maybeUndefined(info.i_winstreak) }} | {{ maybeUndefined(info.e_winstreak) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.maxDifficulty')" :span="3">
                        {{ info.max_difficulty }}
                    </ElDescriptionsItem>
                </ElDescriptions>
            </ElCarouselItem>
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('local.experience')" :span="3">
                        {{ info.experience }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.arenaPoint')" :span="3">
                        {{ info.arena_point }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.win')" :span="3">
                        {{ info.win }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.lastSeason')" :span="3">
                        {{ info.last_season }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.gameCount')" :span="3">
                        {{ maybeUndefined(info.game_count) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.seasonCount')" :span="3">
                        {{ maybeUndefined(info.season_count) }}
                    </ElDescriptionsItem>
                </ElDescriptions>
            </ElCarouselItem>
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('local.noGuessTime')" :span="3">
                        {{ ms_to_s(info.b_ng_t_ms) }} | {{ ms_to_s(info.i_ng_t_ms) }} | {{ ms_to_s(info.e_ng_t_ms) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.endurance')" :span="3">
                        {{ formatDuration(info.b_endurance_ms) }} | {{ formatDuration(info.i_endurance_ms) }} | {{ formatDuration(info.e_endurance_ms) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.standardWins')" :span="3">
                        {{ maybeUndefined(info.b_win) }} | {{ maybeUndefined(info.i_win) }} | {{ maybeUndefined(info.e_win) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.noGuessWins')" :span="3">
                        {{ maybeUndefined(info.b_ng_win) }} | {{ maybeUndefined(info.i_ng_win) }} | {{ maybeUndefined(info.e_ng_win) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.noFlagWins')" :span="3">
                        {{ maybeUndefined(info.win_nf) }}
                    </ElDescriptionsItem>
                </ElDescriptions>
            </ElCarouselItem>
            <ElCarouselItem>
                <ElDescriptions border>
                    <ElDescriptionsItem :label="t('local.totalExperience')" :span="3">
                        {{ maybeUndefined(info.experience_total) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalMinecoins')" :span="3">
                        {{ maybeUndefined(info.minecoin_total) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalGems')" :span="3">
                        {{ maybeUndefined(info.gem_total) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalArenaCoins')" :span="3">
                        {{ maybeUndefined(info.arena_coin_total) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalPlayTime')" :span="3">
                        {{ formatDuration(info.play_time_ms) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.totalArenaPlayTime')" :span="3">
                        {{ formatDuration(info.arena_play_time_ms) }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem :label="t('local.total3BV')" :span="3">
                        {{ maybeUndefined(info.bbbv_total) }}
                    </ElDescriptionsItem>
                </ElDescriptions>
            </ElCarouselItem>
            <ElCarouselItem v-if="store.user.id == store.player.id">
                <div>
                    <span class="text-large text-regular">
                        {{ t('accountlink.statSummary') }}
                    </span>
                    &nbsp;
                    <ElButton @click="updateLink(); $emit('refresh')">
                        {{ t('accountlink.synchronize') }}
                    </ElButton>
                    &nbsp;
                    <IconTaskStatus :status="taskStatus" />
                    <br>
                    <span class="text-danger text-small">
                        {{ errorMsg }}
                    </span>
                </div>
            </ElCarouselItem>
        </ElCarousel>
        <UnverifiedNotice v-else />
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElButton, ElCarousel, ElCarouselItem, ElDescriptions, ElDescriptionsItem } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import CarouselControl from './CarouselControl.vue';
import UnverifiedNotice from './UnverifiedNotice.vue';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import IconTaskStatus from '@/components/common/IconTaskStatus.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { getAccountLinkUpdateErrorMessageKey, updateAccountLink } from '@/services/accountLinkService';
import { store } from '@/store';
import { ms_to_s } from '@/utils';
import { AccountLinkPlatform, AccountWoM } from '@/utils/accountlinks';
import type { TaskStatus } from '@/utils/common/structInterface';
import { formatSecondsAsHMS, toISODateTimeString } from '@/utils/datetime';

defineProps({
    id: { type: String, default: '0' },
    verified: { type: Boolean, default: false },
    info: { type: AccountWoM, default: () => new AccountWoM() },
});

defineEmits(['refresh']);

const refCarousel = useTemplateRef<typeof ElCarousel>('refCarousel');
const errorMsg = ref('');
const taskStatus = ref<TaskStatus>('');
const carouselLength = computed(() => (store.player.id == store.user.id ? 5 : 4));

function maybeUndefined(value?: number) {
    return value ?? '-';
}

function maybeUndefinedToFixed(value?: number, fractionDigits?: number) {
    return value === undefined ? '-' : value.toFixed(fractionDigits);
}

function formatDuration(value?: number) {
    return value === undefined ? '-' : formatSecondsAsHMS(value / 1000);
}

async function updateLink() {
    taskStatus.value = 'loading';
    await updateAccountLink(AccountLinkPlatform.WoM).then(function (data) {
        errorMsg.value = '';
        taskStatus.value = data.type;
        if (data.type == 'error') {
            errorMsg.value = t('accountlink.updateError.title') + t('punct.colon') + t(getAccountLinkUpdateErrorMessageKey(data.category));
        }
    }).catch(function (error: unknown) {
        errorMsg.value = '';
        taskStatus.value = 'error';
        httpErrorNotification(error);
    });
}

/* 本地化 Localization */
const i18nMessage = {
    'zh-cn': { local: {
        arenaPoint: '竞技场',
        experience: '经验',
        lastSeason: '最近赛季',
        maxDifficulty: '高难',
        trophy: '奖杯',
        win: '总胜场',
        gameCount: '游戏局数',
        seasonCount: '参与赛季数',
        noGuessTime: '无猜时间（初/中/高）',
        endurance: '耐力用时（初/中/高）',
        standardWins: '标准胜场（初/中/高）',
        noGuessWins: '无猜胜场（初/中/高）',
        noFlagWins: '无旗胜场',
        totalExperience: '累计获得经验',
        totalMinecoins: '累计获得雷币',
        totalGems: '累计获得宝石',
        totalArenaCoins: '累计获得竞技场币',
        totalPlayTime: '累计游戏用时',
        totalArenaPlayTime: '累计竞技场用时',
        total3BV: '累计 3BV',
    } },
    en: { local: {
        arenaPoint: 'Arena',
        experience: 'Experience',
        lastSeason: 'Last Season',
        maxDifficulty: 'Max Difficulty',
        trophy: 'Trophies',
        win: 'Wins',
        gameCount: 'Games',
        seasonCount: 'Seasons Played',
        noGuessTime: 'NG Time (B/I/E)',
        endurance: 'Endurance Time (B/I/E)',
        standardWins: 'Standard Wins (B/I/E)',
        noGuessWins: 'NG Wins (B/I/E)',
        noFlagWins: 'NF Wins',
        totalExperience: 'Lifetime Experience Earned',
        totalMinecoins: 'Lifetime Minecoins Earned',
        totalGems: 'Lifetime Gems Earned',
        totalArenaCoins: 'Lifetime Arena Coins Earned',
        totalPlayTime: 'Total Play Time',
        totalArenaPlayTime: 'Total Arena Play Time',
        total3BV: 'Total 3BV',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>
