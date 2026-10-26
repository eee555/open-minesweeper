<template>
    <BaseCardNormal>
        <div class="mineracer-link">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('common.platform.m') }}
                    </span>
                </template>
                <template v-if="session" #end>
                    <ElTag :type="statusTagType">
                        {{ t(`local.status.${session.status}`) }}
                    </ElTag>
                </template>
            </PrToolbar>

            <ElSteps :active="activeStep" :finish-status="finishStatus" :process-status="processStatus" align-center>
                <ElStep :title="t('local.stepCreate')" />
                <ElStep :title="t('common.button.confirm')" />
                <ElStep :title="t('local.stepComplete')" />
            </ElSteps>

            <div class="mineracer-body">
                <ElButton v-if="showStartButton" type="primary" :loading="startLoading" @click="startLink">
                    {{ t(session ? 'local.generateNewLink' : 'local.generateLink') }}
                </ElButton>

                <template v-if="session">
                    <ElDescriptions border :column="1" size="small">
                        <ElDescriptionsItem :label="t('common.prop.status')">
                            {{ t(`local.status.${session.status}`) }}
                        </ElDescriptionsItem>
                        <ElDescriptionsItem v-if="session.status == 'pending'" :label="t('local.expiresIn')">
                            {{ remainingTimeText }}
                        </ElDescriptionsItem>
                        <ElDescriptionsItem v-if="session.remote_userid" :label="t('local.userId')">
                            {{ session.remote_userid }}
                        </ElDescriptionsItem>
                    </ElDescriptions>

                    <div v-if="session.status == 'pending'" class="mineracer-actions">
                        <ElLink :href="session.verification_uri_complete" target="_blank" rel="noopener noreferrer" type="primary" :underline="false">
                            <BaseIconExternal />
                            {{ t('local.openLink') }}
                        </ElLink>
                        <ElButton text :loading="statusLoading" @click="pollSession">
                            <BaseIconRefresh />
                            {{ t('local.refreshStatus') }}
                        </ElButton>
                    </div>
                </template>

                <ElAlert v-if="messageKey" :title="t(`local.msg.${messageKey}`)" :type="messageType" show-icon :closable="false" />
            </div>
        </div>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import '@/styles/text.css';

import { ElAlert, ElButton, ElDescriptions, ElDescriptionsItem, ElLink, ElStep, ElSteps, ElTag } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { BaseIconExternal, BaseIconRefresh } from '@/components/common/icon';
import { httpErrorNotification } from '@/components/Notifications';
import { fetchMineracerAccountLinkSession, getMineracerAccountLinkHttpErrorCategory, startMineracerAccountLinkSession } from '@/services/mineracerService';
import type { MineracerAccountLinkSession } from '@/utils/accountlinks';
import { globalNow } from '@/utils/datetime';

const emit = defineEmits<{
    refresh: [];
}>();

const MINERACER_FALLBACK_POLL_DELAY_MS = 2500;
const MINERACER_MIN_POLL_DELAY_MS = 500;

const session = ref<MineracerAccountLinkSession>();
const startLoading = ref(false);
const statusLoading = ref(false);
const httpErrorMessageKey = ref('');
let pollTimer: number | undefined;
let refreshedSessionId = '';

const showStartButton = computed(() => session.value === undefined || ['expired', 'failed'].includes(session.value.status));
const activeStep = computed(() => {
    if (session.value === undefined) return 0;
    if (session.value.status === 'confirmed') return 3;
    if (session.value.status === 'pending') return 1;
    return 2;
});
const finishStatus = computed(() => {
    return session.value?.status === 'failed' ? 'error' : 'success';
});
const processStatus = computed(() => {
    return ['expired', 'failed'].includes(session.value?.status ?? '') ? 'error' : 'process';
});
const statusTagType = computed(() => {
    if (session.value?.status === 'confirmed') return 'success';
    if (session.value?.status === 'failed') return 'danger';
    if (session.value?.status === 'expired') return 'info';
    return 'warning';
});
const remainingTimeText = computed(() => formatRemainingTime((session.value?.expires_at.getTime() ?? 0) - globalNow.value.getTime()));
const messageKey = computed(() => {
    if (httpErrorMessageKey.value) return httpErrorMessageKey.value;
    if (session.value?.status === 'failed') return session.value.error_category;
    if (session.value?.status === 'expired') return 'expired';
    if (session.value?.status === 'pending' && session.value.error_category) return session.value.error_category;
    if (session.value?.status === 'confirmed') return 'linkSuccess';
    return '';
});
const messageType = computed(() => {
    if (session.value?.status === 'confirmed') return 'success';
    if (session.value?.status === 'pending') return 'warning';
    return 'error';
});

async function startLink() {
    clearPollTimer();
    httpErrorMessageKey.value = '';
    startLoading.value = true;
    try {
        applySession(await startMineracerAccountLinkSession());
    } catch (error) {
        handleHttpError(error);
    } finally {
        startLoading.value = false;
    }
}

async function pollSession() {
    const currentSession = session.value;
    if (currentSession?.status !== 'pending' || statusLoading.value) return;
    clearPollTimer();
    httpErrorMessageKey.value = '';
    statusLoading.value = true;
    try {
        applySession(await fetchMineracerAccountLinkSession(currentSession.session_id));
    } catch (error) {
        handleHttpError(error);
        schedulePoll(MINERACER_FALLBACK_POLL_DELAY_MS);
    } finally {
        statusLoading.value = false;
    }
}

function applySession(nextSession: MineracerAccountLinkSession) {
    session.value = nextSession;
    if (nextSession.status === 'confirmed' && refreshedSessionId !== nextSession.session_id) {
        refreshedSessionId = nextSession.session_id;
        emit('refresh');
    }
    if (nextSession.status === 'pending') {
        schedulePoll();
    } else {
        clearPollTimer();
    }
}

function schedulePoll(delayMs?: number) {
    clearPollTimer();
    const currentSession = session.value;
    if (currentSession?.status !== 'pending') return;
    const nextPollAt = currentSession.next_poll_at?.getTime() ?? Date.now() + MINERACER_FALLBACK_POLL_DELAY_MS;
    const pollAt = Math.min(nextPollAt, currentSession.expires_at.getTime());
    const delay = delayMs ?? Math.max(MINERACER_MIN_POLL_DELAY_MS, pollAt - Date.now());
    pollTimer = window.setTimeout(() => {
        void pollSession();
    }, delay);
}

function clearPollTimer() {
    if (pollTimer === undefined) return;
    window.clearTimeout(pollTimer);
    pollTimer = undefined;
}

function handleHttpError(error: unknown) {
    const category = getMineracerAccountLinkHttpErrorCategory(error);
    if (category === undefined) {
        httpErrorNotification(error);
        return;
    }
    httpErrorMessageKey.value = category;
}

function formatRemainingTime(milliseconds: number): string {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

onBeforeUnmount(clearPollTimer);

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
        stepComplete: '完成',
        stepCreate: '链接',
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
        stepComplete: 'Linked',
        stepCreate: 'Link',
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
