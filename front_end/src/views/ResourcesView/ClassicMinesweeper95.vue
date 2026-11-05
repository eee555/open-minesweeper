<template>
    <div>
        <span class="text-medium">
            {{ t('local.description') }}
            <VideoStateIcon :state="MS_State.Frozen" />
        </span>
        <div style="height: 1em" />
        <div class="description-layout">
            <dl class="descriptions descriptions-bordered">
                <div class="description-item description-span-2">
                    <dt>{{ t('software.platform') }}</dt>
                    <dd>{{ t('software.wechat') }}</dd>
                </div>
                <div class="description-item">
                    <dt>{{ t('software.supportedLanguages') }}</dt>
                    <dd>
                        <BaseFlagCN />
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('software.feature') }}</dt>
                    <dd>
                        <BaseTagSupport :support="false">
                            {{ t('software.features.customMode') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            {{ t('software.features.customCounter') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            {{ t('software.features.noGuessing') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            {{ t('software.features.cellScale') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            {{ t('software.features.tournament') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            {{ t('software.features.mouseLock') }}
                        </BaseTagSupport>
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('software.platform') }}</dt>
                    <dd>
                        <BaseTagSupport>
                            <BaseBadgeOpenms />
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            <BaseBadgeSaolei />
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            <BaseBadgeMsgames />
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            <BaseBadgeScoreganizer />
                        </BaseTagSupport>
                    </dd>
                </div>
            </dl>
        </div>
        <div style="height: 1em" />
        <img :src="Classic95">
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/link.css';
import { useI18n } from 'vue-i18n';

import Classic95 from '@/assets/classic95link.jpg';
import { BaseBadgeMsgames, BaseBadgeOpenms, BaseBadgeSaolei, BaseBadgeScoreganizer } from '@/components/common/badge';
import BaseTagSupport from '@/components/common/BaseTagSupport.vue';
import { BaseFlagCN } from '@/components/common/flag';
import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { MS_State } from '@/utils/ms_const';

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        description: '《95经典扫雷》是一款新发布的微信小程序，支持EVF导出、关联开源扫雷网账号、录像上传开源扫雷网。有新手教程，可休闲，可竞速、对战。每年分四赛季，优胜者可得小礼品。由于其安全性有待检验，目前通过其上传的录像暂时标记为',
    } },
    en: { local: {
        description: 'Classic Minesweeper 95 is a newly released WeChat Mini Program that supports EVF export, Open Minesweeper account link & video upload. It includes a tutorial and a PVP mode. It has 4 seasons each year, and the winner can get a prize. Since its reliability is yet to be tested, the videos uploaded through it are temporarily marked as ',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
