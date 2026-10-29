<template>
    <span v-if="platform == AccountLinkPlatform.Saolei">
        <b>{{ t('local.title') }}</b><br>
        {{ t('local.saolei1') }}
        <PlatformIcon platform="c" />{{ t('local.saolei2') }}<br>
        <img src="../../assets/IdGuideSaolei.png" width="100%">
    </span>
    <span v-else-if="platform == AccountLinkPlatform.MSGames">
        <b>{{ t('local.title') }}</b><br>
        {{ t('local.msgames1') }}
        <PlatformIcon platform="a" />{{ t('local.msgames2') }}<br>
        <img src="../../assets/IdGuideMsgames1.png" width="100%">
        {{ t('local.msgames3') }}
        <img src="../../assets/IdGuideMsgames2.png" width="100%">
    </span>
    <span v-else-if="platform == AccountLinkPlatform.WoM">
        <b>{{ t('local.title') }}</b><br>
        {{ t('local.wom1') }}
        <PlatformIcon platform="w" />{{ t('local.wom2') }}
        <img src="../../assets/IdGuideWom.png" width="100%">
    </span>
    <span v-else-if="platform == AccountLinkPlatform.QQ">
        {{ t('local.QQ') }}
    </span>
    <span v-else-if="platform == AccountLinkPlatform.Bilibili">
        <b>{{ t('local.title') }}</b><br>
        {{ t('local.bilibili1') }}
        <PlatformIcon platform="B" />{{ t('local.bilibili2') }}<br>
        <b class="text-warning">{{ t('local.privacyTitle') }}</b>
        {{ t('local.bilibiliPrivacy') }}
        <img src="../../assets/IdGuideBilibili.png" width="100%">
    </span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import PlatformIcon from '@/components/widgets/PlatformIcon.vue';
import { AccountLinkPlatform } from '@/utils/accountlinks';
import type { AccountLinkPlatform as AccountLinkPlatformType } from '@/utils/accountlinks';

defineProps({
    platform: {
        type: String as PropType<AccountLinkPlatformType>,
        required: true,
    },
});

const i18nMessages = {
    'zh-cn': { local: {
        msgames1: '在',
        msgames2: '排行榜找到你的位置：',
        msgames3: '在上图点击名字右边的链接，进入如下的个人主页，网址结尾的数字就是ID。',
        bilibili1: '进入',
        bilibili2: '个人空间，网址 space.bilibili.com/ 后面的数字就是 UID。',
        bilibiliPrivacy: '本网站账号使用实名展示。关联 Bilibili 后，其他用户可能将你的 Bilibili 账号与你的实名身份联系起来。',
        QQ: 'QQ号信息网站管理员可见。请注意隐私安全。',
        privacyTitle: '隐私提醒：',
        saolei1: '登录',
        saolei2: '，进入“我的地盘”，ID位置如下图所示。',
        title: '如何找到ID',
        wom1: '在',
        wom2: '进入你的个人主页，网址结尾的数字就是你的ID。',
    } },
    en: { local: {
        msgames1: 'Find yourself on the ',
        msgames2: ' ranking:',
        msgames3: 'Click the link next to your name (see image above) to get to your profile (see image below). The number at the end of the url is your ID.',
        bilibili1: 'Open your profile on ',
        bilibili2: '. The number after space.bilibili.com/ is your UID.',
        bilibiliPrivacy: 'This site displays accounts under real names. Linking Bilibili may allow others to connect your Bilibili account with your real-name identity.',
        QQ: 'The QQ number is accessible from site moderators. Please be aware of your privacy safety.',
        privacyTitle: 'Privacy notice: ',
        saolei1: 'Go to your profile page on ',
        saolei2: '. The positions of the ID are shown below.',
        title: 'How to locate the ID',
        wom1: 'Go to your profile page on ',
        wom2: '. The number at the end of the url is your ID.',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
