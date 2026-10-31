<template>
    <div class="section-label">
        <strong>{{ t('local.owner') }}</strong>
    </div>
    <div class="section-body">
        <PlayerName :user-id="1" />
    </div>
    <div class="section-label">
        <strong>{{ t('local.moderator') }}</strong>
    </div>
    <div class="section-body">
        <PlayerName :user-id="2" />
        <PlayerName :user-id="24" />
        <PlayerName :user-id="44" />
        <PlayerName :user-id="82" />
        <PlayerName :user-id="114" />
    </div>
    <div class="section-label">
        <strong>{{ t('local.software') }}</strong>
    </div>
    <div class="section-body">
        <GitHubUser username="putianyi889" />
        <GitHubUser username="eee555" />
        <GitHubUser username="Threeeee" />
        <GitHubUser username="ljzloser" />
        <GitHubUser username="hwatson381" />
        <GitHubUser username="hgraceb" />
        <GitHubUser username="LockhartANR" />
        <GitHubUser username="Corday-nkusky" />
    </div>
    <div class="section-label">
        <strong>{{ t('local.localization') }}</strong>
    </div>
    <div class="section-body">
        <div>
            {{ t('local.zhCn') }}
            <GitHubUser username="putianyi889" />
        </div>
        <div>
            {{ t('local.en') }}
            <GitHubUser username="putianyi889" />
        </div>
        <div>
            {{ t('local.de') }}
            <GitHubUser username="auk3" />
        </div>
        <div>
            {{ t('local.pl') }}
            <GitHubUser username="kiraa96" />
        </div>
    </div>
    <div class="section-label">
        <strong>{{ t('local.acknowledgement') }}</strong>
    </div>
    <div class="section-body">
        <span v-for="item in acknowledgements" style="padding-right: 10px">
            {{ item.text }}
        </span>
    </div>
</template>

<script lang="ts" setup>
import '@/styles/layout.css';
// 注册、登录的弹框及右上方按钮
import { useI18n } from 'vue-i18n';

import PlayerName from '@/components/PlayerName.vue';
import GitHubUser from '@/components/widgets/GitHubUser.vue';

// 积分系统完成后需要加jsd
const acknowledgements = [
    { text: 'T0nyX1ang' },
    { text: 'Pulsar' },
    { text: 'darkness' },
    { text: 'lc4337' },
    { text: '冰糖雪梨' },
    { text: '生命★是┗ 〓┛是☆什么' },
    { text: 'Arya' },
    { text: 'StrangeDust' },
    { text: 'jabajop' },
    { text: 'qqwref' },
    { text: 'gacord' },
    { text: 'Nanaka.' },
    { text: '购置拆解' },
    { text: '毛毛虫' },
    { text: '铧嵇' },
];

/* 本地化 Localization */
const i18nMessage = {
    'zh-cn': { local: {
        owner: '站长',
        moderator: '管理员',
        software: '开发',
        localization: '本地化',
        zhCn: '简体中文',
        en: '英语',
        de: '德语',
        pl: '波兰语',
        designer: '外观设计',
        acknowledgement: '致谢',
    } },
    en: { local: {
        owner: 'Owner',
        moderator: 'Moderators',
        software: 'Developers',
        localization: 'Localization',
        zhCn: 'Simplified Chinese',
        en: 'English',
        de: 'German',
        pl: 'Polish',
        designer: 'UI designers',
        acknowledgement: 'Acknowledgement',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>

<style scoped>
.thanks-section {
    border-top: 1px solid var(--ui-border-color);
    margin-top: 24px;
    padding-top: 24px;
}

.section-label {
    padding-bottom: 5px;
}

.section-body {
    display: flex;
    gap: 2rem;
    margin-bottom: 15px;
}
</style>
