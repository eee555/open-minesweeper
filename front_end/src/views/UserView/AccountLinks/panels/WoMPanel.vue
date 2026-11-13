<template>
    <div class="account-panel">
        <div style="margin-bottom: 0.5em;" />
        <div v-if="verified" class="account-sections">
            <section class="account-section">
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('prop.update_time') }}</dt><dd>
                                {{ toISODateTimeString(info.update_time) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.trophy') }}</dt><dd>
                                {{ info.trophy }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.time') }}</dt><dd>
                                {{ ms_to_s(info.b_t_ms) }} | {{ ms_to_s(info.i_t_ms) }} | {{ ms_to_s(info.e_t_ms) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.ioe') }}</dt><dd>
                                {{ maybeUndefinedToFixed(info.b_ioe, 2) }} | {{ maybeUndefinedToFixed(info.i_ioe, 2) }} | {{ maybeUndefinedToFixed(info.e_ioe, 2) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.mastery') }}</dt><dd>
                                {{ maybeUndefined(info.b_mastery) }} | {{ maybeUndefined(info.i_mastery) }} | {{ maybeUndefined(info.e_mastery) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('prop.winstreak') }}</dt><dd>
                                {{ maybeUndefined(info.b_winstreak) }} | {{ maybeUndefined(info.i_winstreak) }} | {{ maybeUndefined(info.e_winstreak) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.maxDifficulty') }}</dt><dd>
                                {{ info.max_difficulty }}
                            </dd>
                        </div>
                    </dl>
                </div>
            </section>
            <section class="account-section">
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('local.experience') }}</dt><dd>
                                {{ info.experience }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.arenaPoint') }}</dt><dd>
                                {{ info.arena_point }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.win') }}</dt><dd>
                                {{ info.win }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.lastSeason') }}</dt><dd>
                                {{ info.last_season }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.gameCount') }}</dt><dd>
                                {{ maybeUndefined(info.game_count) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.seasonCount') }}</dt><dd>
                                {{ maybeUndefined(info.season_count) }}
                            </dd>
                        </div>
                    </dl>
                </div>
            </section>
            <section class="account-section">
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('local.noGuessTime') }}</dt><dd>
                                {{ ms_to_s(info.b_ng_t_ms) }} | {{ ms_to_s(info.i_ng_t_ms) }} | {{ ms_to_s(info.e_ng_t_ms) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.endurance') }}</dt><dd>
                                {{ formatDuration(info.b_endurance_ms) }} | {{ formatDuration(info.i_endurance_ms) }} | {{ formatDuration(info.e_endurance_ms) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.standardWins') }}</dt><dd>
                                {{ maybeUndefined(info.b_win) }} | {{ maybeUndefined(info.i_win) }} | {{ maybeUndefined(info.e_win) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.noGuessWins') }}</dt><dd>
                                {{ maybeUndefined(info.b_ng_win) }} | {{ maybeUndefined(info.i_ng_win) }} | {{ maybeUndefined(info.e_ng_win) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.noFlagWins') }}</dt><dd>
                                {{ maybeUndefined(info.win_nf) }}
                            </dd>
                        </div>
                    </dl>
                </div>
            </section>
            <section class="account-section">
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('local.totalExperience') }}</dt><dd>
                                {{ maybeUndefined(info.experience_total) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.totalMinecoins') }}</dt><dd>
                                {{ maybeUndefined(info.minecoin_total) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.totalGems') }}</dt><dd>
                                {{ maybeUndefined(info.gem_total) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.totalArenaCoins') }}</dt><dd>
                                {{ maybeUndefined(info.arena_coin_total) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.totalPlayTime') }}</dt><dd>
                                {{ formatDuration(info.play_time_ms) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.totalArenaPlayTime') }}</dt><dd>
                                {{ formatDuration(info.arena_play_time_ms) }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.total3BV') }}</dt><dd>
                                {{ maybeUndefined(info.bbbv_total) }}
                            </dd>
                        </div>
                    </dl>
                </div>
            </section>
            <section v-if="owner" class="account-section">
                <div>
                    <span class="text-large text-regular">
                        {{ t('accountlink.statSummary') }}
                    </span>
                    &nbsp;
                    <BaseButton @click="updateLink()">
                        {{ t('accountlink.synchronize') }}
                    </BaseButton>
                    &nbsp;
                    <IconTaskStatus :status="taskStatus" />
                    <br>
                    <span class="text-danger text-small">
                        {{ errorMsg }}
                    </span>
                </div>
            </section>
        </div>
        <UnverifiedNotice v-else />
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';

import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { useActivePanel } from '../useActivePanel';

import UnverifiedNotice from '@/components/accountlinks/UnverifiedNotice.vue';
import BaseButton from '@/components/common/BaseButton.vue';
import IconTaskStatus from '@/components/common/IconTaskStatus.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { getAccountLinkUpdateErrorMessageKey, updateAccountLink } from '@/services/accountLinkService';
import { store } from '@/store';
import { ms_to_s } from '@/utils';
import { AccountLinkPlatform, AccountWoM } from '@/utils/accountlinks';
import type { TaskStatus } from '@/utils/common/structInterface';
import { formatSecondsAsHMS, toISODateTimeString } from '@/utils/datetime';

defineProps({
    owner: { type: Boolean, default: false },
    verified: { type: Boolean, default: false },
    info: { type: AccountWoM, default: () => new AccountWoM() },
});

const emit = defineEmits(['refresh']);
const isActive = useActivePanel();

const errorMsg = ref('');
const taskStatus = ref<TaskStatus>('');
const targetUserId = computed(() => (store.isMemorialProfileAdmin ? store.player.id : undefined));

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
    if (taskStatus.value === 'loading') return;
    taskStatus.value = 'loading';
    await updateAccountLink(AccountLinkPlatform.WoM, targetUserId.value).then(function (data) {
        if (!isActive()) return;
        errorMsg.value = '';
        taskStatus.value = data.type;
        if (data.type === 'success') emit('refresh');
        if (data.type == 'error') {
            errorMsg.value = t('accountlink.updateError.title') + t('punct.colon') + t(getAccountLinkUpdateErrorMessageKey(data.category));
        }
    }).catch(function (error: unknown) {
        if (!isActive()) return;
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
