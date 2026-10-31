<template>
    <span class="text-medium">
        <ul>
            <li>
                {{ t('local.line_1_1') }}<SoftwareIcon software="a" />{{ t('local.line_1_2') }}<SoftwareIcon software="e" />{{ t('local.line_1_3') }}
            </li>
            <li>
                {{ t('local.line_2_1') }}
            </li>
            <li>
                {{ t('local.line_3_1') }}<VideoStateIcon :state="MS_State.Identifier" />{{ t('local.line_3_2') }}
            </li>
            <li>
                {{ t('local.line_4_1') }}
                <ul>
                    <li>
                        {{ t('local.line_4_2') }}
                    </li>
                    <li>
                        {{ t('local.line_4_3') }}
                    </li>
                </ul>
                {{ t('local.line_4_4') }}
            </li>
        </ul>
    </span>
</template>

<script lang="ts" setup>
import { useI18n } from 'vue-i18n';

import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { MS_State } from '@/utils/ms_const';

const componentMessages = {
    'zh-cn': { local: {
        line_1_1: '标识是玩家自己填写的，录像中包含的一段字符串签名。在',
        line_1_2: '的设置中，这被称为“玩家身份标识”。在',
        line_1_3: '的设置中，这被称为“标识”。',
        line_2_1: '每名用户可以拥有不限数量的标识，但是不同用户不能拥有同一标识。用户可以在个人主页修改标识列表。',
        line_3_1: '如果一个录像的标识不在用户的标识列表中，则该录像处于',
        line_3_2: '状态，不参与新闻与排行榜的统计。',
        line_4_1: '当多名用户发生标识冲突的时候，可自行协商或寻求管理员帮助。管理员会基于如下原则作出裁决：',
        line_4_2: '首先保护用户使用自己的实名作为标识的权利；',
        line_4_3: '其次保护先使用该标识的用户。“使用”是指在任何地方（需要可查证）公开发表该标识的录像。',
        line_4_4: '管理员裁决后可能会删除某些用户的对应标识，这会导致用户成绩受损。',
    } },
    en: { local: {
        line_1_1: 'An identifier is a string signature attached to the video file by the player. It is referred to as "Player Identification Text" in the settings of ',
        line_1_2: ' and "Identifier" in the settings of ',
        line_1_3: '.',
        line_2_1: 'Each user can have unlimited number of identifiers, while different users cannot have the same identifier. A user can modify their identifiers at their profile page.',
        line_3_1: 'If the identifier of a video is not included by the user\'s identifier list, then the video is categorized as ',
        line_3_2: ' and ignored by News and Ranking.',
        line_4_1: 'When multiple users face an identifier collision, they can figure out a solution by themselves or contact a moderator for help. The moderator will make a decision based on the following principles:',
        line_4_2: 'Firstly, protect the right of users using their own real name in identifiers;',
        line_4_3: 'Secondly, approve the earlist claim of the identifier, where a claim refers to publishing a video with the identifier anywhere.',
        line_4_4: 'After the decision, some users may lose the identifier, which could result in scores withdrawn from Ranking.',
    } },
};

const { t } = useI18n({
    messages: componentMessages,
});
</script>
