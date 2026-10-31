<template>
    <div>
        <span class="text-medium">
            {{ t('local.description') }}
            <br>
            {{ t('software.repository') }}{{ t('punct.colon') }}
            https://github.com/eee555/Metasweeper
        </span>
        <div style="height: 1em" />
        <div class="description-layout">
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
                        <BaseFlagCN />&nbsp;
                        <BaseFlagUK />&nbsp;
                        <BaseFlagPL />&nbsp;
                        <BaseFlagDE />
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
                        <BaseTagSupport :support="false">
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
        <BaseTable>
            <template #head>
                <tr>
                    <th scope="col">
                        {{ t('software.version') }}
                    </th>
                    <th scope="col">
                        {{ t('software.releaseDate') }}
                    </th>
                    <th scope="col">
                        {{ t('software.expireDate') }}
                    </th>
                    <th scope="col">
                        {{ t('software.download') }}
                    </th>
                </tr>
            </template>
            <tr v-for="row in tableData" :key="row.version">
                <td>{{ row.version }}</td>
                <td>{{ row.date }}</td>
                <td>{{ row.expire }}</td>
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
import { BaseFlagCN, BaseFlagDE, BaseFlagPL, BaseFlagUK } from '@/components/common/flag';

const tableData = [
    {
        version: 'v3.3.4',
        date: '2026-8-11',
        expire: '-',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metasweeper-3.3.4.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.3.4/Metasweeper-3.3.4.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.3.4/Metasweeper-3.3.4.exe',
            },
        ],
    },
    {
        version: 'v3.3.3',
        date: '2026-7-10',
        expire: '-',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metasweeper-3.3.3.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.3.3/Metasweeper-3.3.3.exe',
            },
        ],
    },
    {
        version: 'v3.3.2',
        date: '2026-7-7',
        expire: '-',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metasweeper-3.3.2.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.3.2/Metasweeper-3.3.2.exe',
            },
        ],
    },
    {
        version: 'v3.3.1',
        date: '2026-6-25',
        expire: '-',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metasweeper-3.3.1.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.3.1/Metasweeper-3.3.1.exe',
            },
        ],
    },
    {
        version: 'v3.2.2',
        date: '2026-3-3',
        expire: '-',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metaminesweeper-3.2.2.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.2.2/Metaminesweeper-3.2.2.exe',
            },
        ],
    },
    {
        version: 'v3.2.1',
        date: '2025-11-22',
        expire: '2026-3-3',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metaminesweeper-3.2.1.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.2.1/Metaminesweeper-3.2.1.exe',
            },
        ],
    },
    {
        version: 'v3.2.0',
        date: '2024-11-21',
        expire: '2026-3-3',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metaminesweeper-3.2.0.exe',
            },
            {
                label: 'Gitee',
                url: 'https://gitee.com/ee55/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.2.0/Metaminesweeper-3.2.0.exe',
            },
        ],
    },
    {
        version: 'v3.1.11',
        date: '2024-9-10',
        expire: '2026-3-3',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metaminesweeper-v3.1.11.zip',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.1.11/Metaminesweeper-v3.1.11.zip',
            },
        ],
    },
    {
        version: 'v3.1.9',
        date: '2024-7-27',
        expire: '2026-3-3',
        links: [
            {
                label: 'OpenMS',
                url: 'https://openms.top/download/Metaminesweeper-v3.1.9.zip',
            },
            {
                label: 'GitHub',
                url: 'https://github.com/eee555/Metasweeper/releases/download/3.1.9/Metaminesweeper-v3.1.9.zip',
            },
        ],
    },
];

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        description: '元扫雷是一款开源扫雷软件，正处于活跃更新中。',
    } },
    en: { local: {
        description: 'Metasweeper is an open-source minesweeper clone under active development.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
