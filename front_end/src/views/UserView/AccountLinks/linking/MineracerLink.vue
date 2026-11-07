<template>
    <div class="account-panel">
        <div class="mineracer-link">
            <div class="mineracer-body">
                <BaseButton v-if="showStartButton" type="primary" :loading="startLoading" @click="startLink">
                    {{ t(session ? 'local.generateNewLink' : 'local.generateLink') }}
                </BaseButton>

                <template v-if="session">
                    <div class="description-layout">
                        <dl class="descriptions descriptions-bordered">
                            <div class="description-item">
                                <dt>{{ t('prop.status') }}</dt><dd>
                                    {{ t(`local.status.${session.status}`) }}
                                </dd>
                            </div>
                            <div v-if="session.status == 'pending'" class="description-item">
                                <dt>{{ t('local.expiresIn') }}</dt><dd>
                                    {{ remainingTimeText }}
                                </dd>
                            </div>
                            <div v-if="session.remote_userid" class="description-item">
                                <dt>{{ t('local.userId') }}</dt><dd>
                                    {{ session.remote_userid }}
                                </dd>
                            </div>
                        </dl>
                    </div>

                    <div v-if="session.status == 'pending'" class="mineracer-actions">
                        <a class="link" :href="session.verification_uri_complete" target="_blank" rel="noopener noreferrer">
                            <BaseIconExternal />
                            {{ t('local.openLink') }}
                        </a>
                        <BaseButton text :loading="statusLoading" @click="pollSession">
                            <BaseIconRefresh />
                            {{ t('local.refreshStatus') }}
                        </BaseButton>
                    </div>
                </template>

                <p v-if="messageKey" role="status" :class="messageType === 'success' ? 'text-success' : 'text-danger'">
                    {{ t(`local.msg.${messageKey}`) }}
                </p>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/link.css';
import '../page.css';
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { useMineracerLink } from './useMineracerLink';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconExternal, BaseIconRefresh } from '@/components/common/icon';
import { globalNow } from '@/utils/datetime';

const props = defineProps({ flow: { type: Object as PropType<ReturnType<typeof useMineracerLink>>, required: true } });
const { session, startLoading, statusLoading, httpErrorMessageKey, startLink, pollSession } = props.flow;
const showStartButton = computed(() => session.value === undefined || ['expired', 'failed'].includes(session.value.status));
const remainingTimeText = computed(() => {
    const seconds = Math.max(0, Math.ceil(((session.value?.expires_at.getTime() ?? 0) - globalNow.value.getTime()) / 1000));
    return Math.floor(seconds / 60) + ':' + (seconds % 60).toString().padStart(2, '0');
});
const messageKey = computed(() => httpErrorMessageKey.value || (session.value?.status === 'confirmed' ? 'linkSuccess' : session.value?.status === 'expired' ? 'expired' : session.value?.error_category ?? ''));
const messageType = computed(() => (session.value?.status === 'confirmed' ? 'success' : 'error'));

const i18nMessages = {
    'zh-cn': { local: {
        expiresIn: '剩余时间',
        generateLink: '生成关联链接',
        generateNewLink: '重新生成链接',
        msg: {
            account_not_found: 'Mineracer 找不到该关联链接对应的账号。',
            already_linked: '已经关联了 Mineracer 账号。',
            expired: '关联链接已过期。',
            identifier_conflict: '该 Mineracer 账号已被其他用户绑定。',
            invalid_device_code: 'Mineracer 已无法识别该关联链接，请重新生成。',
            linkSuccess: 'Mineracer 账号关联成功。',
            link_superseded: '该 Mineracer 关联链接已被新的流程替代，请重新生成链接。',
            not_configured: 'Mineracer 关联尚未配置。',
            pending_start: '正在创建 Mineracer 关联链接，请稍后再试。',
            remote_failed: 'Mineracer 未能完成确认。',
            requestexception: '请求 Mineracer 失败。',
            response: 'Mineracer 返回了无法识别的响应。',
            timeout: 'Mineracer 响应超时。',
            unknown: 'Mineracer 关联失败。',
        },
        openLink: '打开链接',
        refreshStatus: '刷新状态',
        status: {
            confirmed: '已关联',
            expired: '已过期',
            failed: '关联失败',
            pending: '等待 Mineracer 确认',
        },
        userId: 'Mineracer 用户 ID',
    } },
    en: { local: {
        expiresIn: 'Expires in',
        generateLink: 'Generate link',
        generateNewLink: 'Generate new link',
        msg: {
            account_not_found: 'Mineracer could not find the account for this link.',
            already_linked: 'A Mineracer account is already linked.',
            expired: 'The link has expired.',
            identifier_conflict: 'This Mineracer account is already linked to another user.',
            invalid_device_code: 'Mineracer no longer recognises this link. Please generate a new one.',
            linkSuccess: 'Mineracer account linked.',
            link_superseded: 'This Mineracer link was replaced by a newer one. Please generate a new link.',
            not_configured: 'Mineracer linking is not configured.',
            pending_start: 'A Mineracer link is already being created. Please try again shortly.',
            remote_failed: 'Mineracer could not confirm the link.',
            requestexception: 'Failed to request Mineracer.',
            response: 'Mineracer returned an unrecognised response.',
            timeout: 'Mineracer did not respond in time.',
            unknown: 'Mineracer linking failed.',
        },
        openLink: 'Open link',
        refreshStatus: 'Refresh status',
        status: {
            confirmed: 'Linked',
            expired: 'Expired',
            failed: 'Failed',
            pending: 'Waiting for Mineracer',
        },
        userId: 'Mineracer User ID',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.mineracer-link {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0;
}

.mineracer-body {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.mineracer-actions {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}
</style>
