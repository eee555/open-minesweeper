<template>
    <div>
        <span class="text-medium">
            {{ t('local.description') }}
        </span>
        <div style="height: 1em" />
        <div class="description-layout" style="max-width: 600px">
            <dl class="descriptions descriptions-bordered">
                <div class="description-item description-span-2">
                    <dt>{{ t('software.operatingSystem') }}</dt>
                    <dd>
                        Windows
                    </dd>
                </div>
                <div class="description-item">
                    <dt>{{ t('software.supportedLanguages') }}</dt>
                    <dd>
                        <BaseFlagUK />&nbsp;<BaseFlagCN />&nbsp;<BaseFlagJP />
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('software.feature') }}</dt>
                    <dd>
                        <BaseTagSupport>
                            {{ t('software.features.customMode') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            {{ t('software.features.customCounter') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            {{ t('software.features.noGuessing') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            {{ t('software.features.cellScale') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
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
                        <BaseTagSupport>
                            <BaseBadgeMsgames />
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport>
                            <BaseBadgeScoreganizer />
                        </BaseTagSupport>
                    </dd>
                </div>
            </dl>
        </div>
        <div style="height: 1em" />
        <BaseTable style="max-width: 600px">
            <template #head>
                <tr>
                    <th scope="col">
                        {{ t('software.version') }}
                    </th>
                    <th scope="col">
                        {{ t('software.releaseDate') }}
                    </th>
                    <th scope="col">
                        {{ t('software.download') }}
                    </th>
                </tr>
            </template>
            <tr v-for="row in tableData" :key="row.version">
                <td>{{ row.version }}</td>
                <td>{{ row.date }}</td>
                <td>
                    <template v-for="link in row.links" :key="link.url">
                        <a class="link text" :href="link.url" target="_blank" rel="noopener noreferrer">
                            {{ link.label }}
                        </a>
                        &nbsp;
                    </template>
                </td>
            </tr>
        </BaseTable>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/link.css';
import { useI18n } from 'vue-i18n';

import { BaseBadgeMsgames, BaseBadgeOpenms, BaseBadgeSaolei, BaseBadgeScoreganizer } from '@/components/common/badge';
import BaseTable from '@/components/common/BaseTable.vue';
import BaseTagSupport from '@/components/common/BaseTagSupport.vue';
import { BaseFlagCN, BaseFlagJP, BaseFlagUK } from '@/components/common/flag';

const tableData = [
    {
        version: '0.52.3',
        date: 'Unknown',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Arbiter_0.52.3.zip',
            },
            {
                label: 'Saolei',
                url: 'http://saolei.wang/Download/Arbiter_0.52.3.zip',
            },
            {
                label: 'MSGames',
                url: 'https://minesweepergame.com/download/arbiter.zip',
            },
        ],
    },
];

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        description: 'Minesweeper Arbiter 是最流行的专业扫雷软件。',
    } },
    en: { local: {
        description: 'Minesweeper Arbiter is the most popular authoritative minesweeper clone.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
