<template>
    <div class="account-panel">
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
                            <dt>{{ t('local.name') }}</dt><dd>
                                {{ info.name }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.officialTitle') }}</dt><dd>
                                {{ info.official_title }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.level') }}</dt><dd>
                                {{ info.level }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.videoCount') }}</dt><dd>
                                {{ info.video_count }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.following') }}</dt><dd>
                                {{ info.following }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.articleCount') }}</dt><dd>
                                {{ info.article_count }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.follower') }}</dt><dd>
                                {{ info.follower }}
                            </dd>
                        </div>
                        <div class="description-item">
                            <dt>{{ t('local.opusCount') }}</dt><dd>
                                {{ info.opus_count }}
                            </dd>
                        </div>
                        <div v-if="info.sign" class="description-item">
                            <dt>{{ t('local.sign') }}</dt><dd>
                                {{ info.sign }}
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
import { AccountBilibili, AccountLinkPlatform } from '@/utils/accountlinks';
import type { TaskStatus } from '@/utils/common/structInterface';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
    owner: { type: Boolean, default: false },
    verified: { type: Boolean, default: false },
    info: { type: AccountBilibili, default: () => new AccountBilibili() },
});

const emit = defineEmits(['refresh']);
const isActive = useActivePanel();

const errorMsg = ref('');
const taskStatus = ref<TaskStatus>('');
const targetUserId = computed(() => (store.isMemorialProfileAdmin ? store.player.id : undefined));

async function updateLink() {
    if (taskStatus.value === 'loading') return;
    taskStatus.value = 'loading';
    await updateAccountLink(AccountLinkPlatform.Bilibili, targetUserId.value).then(function (data) {
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

const i18nMessage = {
    'zh-cn': { local: {
        articleCount: '专栏',
        follower: '粉丝',
        following: '关注',
        level: '等级',
        name: '昵称',
        officialTitle: '认证',
        opusCount: '动态',
        profile: '资料',
        sign: '签名',
        videoCount: '视频',
    } },
    en: { local: {
        articleCount: 'Articles',
        follower: 'Followers',
        following: 'Following',
        level: 'Level',
        name: 'Name',
        officialTitle: 'Identity',
        opusCount: 'Posts',
        profile: 'Profile',
        sign: 'Signature',
        videoCount: 'Videos',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>

<style lang="less" scoped>
.profile-row {
    align-items: center;
    display: flex;
    min-width: 0;
}

.profile-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
}
</style>
