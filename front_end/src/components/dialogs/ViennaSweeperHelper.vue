<template>
    <div>
        <span class="text-medium">
            {{ t('local.description1') }}
            <br>
            {{ t('local.description2') }}
            <br>
            {{ t('software.officialSite') }}{{ t('punct.colon') }}
            https://sweeper.wien
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
                        <BaseFlagUK />
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('software.feature') }}</dt>
                    <dd>
                        <BaseTagSupport>
                            {{ t('software.features.customMode') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
                            {{ t('software.features.customCounter') }}
                        </BaseTagSupport>
                        &nbsp;
                        <BaseTagSupport :support="false">
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
                        <BaseTagSupport :support="false">
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
import { BaseFlagUK } from '@/components/common/flag';

const tableData = [
    {
        version: 'v4.0.0',
        date: '2024-11-15',
        expire: '-',
        links: [
            {
                label: 'Official',
                url: 'https://sweeper.wien/static/downloads/vsweep-4.0.0-vsh-0.1.0.zip',
            },
        ],
    },
    {
        version: 'v5.0.0b4',
        date: '2025-9-7',
        expire: 'Beta',
        links: [
            {
                label: 'Official',
                url: 'https://sweeper.wien/static/downloads/vsweep-5.0.0b4-vsh-0.2.0b2.zip',
            },
        ],
    },
    {
        version: 'v3.0',
        date: 'Unknown',
        expire: '2023-4-24',
        links: [
            {
                label: 'Saolei',
                url: 'http://saolei.wang/Download/Viennasweeper_3.0.zip',
            },
        ],
    },
];

const i18nMessages = {
    'zh-cn': { local: {
        description1: 'Viennasweeper 是一款专业扫雷软件，它和Scoreganizer的兼容性最好。',
        description2: '从v5.0.0版本开始，Viennasweeper使用了新的录像格式，该格式目前仅被开源扫雷网和Scoreganizer支持。',
    } },
    en: { local: {
        description1: 'Viennasweeper is an official minesweeper clone. It has the best compatibility with Scoreganizer.',
        description2: 'From v5.0.0, Viennasweeper moves to a new replay format that is only currently supported by Open Minesweeper and Scoreganizer.',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
