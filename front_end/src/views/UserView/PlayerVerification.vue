<template>
    <section class="card verification">
        <h2 class="text-large">
            {{ t('local.title') }}
        </h2>
        <div class="verification__status">
            <span>{{ t('local.current') }}{{ t('punct.colon') }}</span>
            <span :class="status?.verified ? 'text-success' : 'text-danger'" data-cy="verification-state">
                {{ status?.verified ? t('local.verified') : t('local.unverified') }}
            </span>
            <span>{{ t('local.access') }}{{ t('punct.colon') }}{{ status?.can_submit_replays ? t('local.allowed') : t('local.blocked') }}</span>
        </div>
        <p class="text-regular text-small">
            {{ t('local.hint') }}
        </p>
        <div class="verification__row">
            <label for="verification-request-id">{{ t('local.requestTo') }}</label>
            <input id="verification-request-id" v-model="requestUserId" class="verification__input" type="number" min="1">
            <BaseButton size="small" :disabled="busy || !status?.can_request" @click="submitRequest">
                {{ t('local.sendRequest') }}
            </BaseButton>
        </div>
        <p class="text-regular text-small" data-cy="verification-request-state">
            {{ requestDescription }}
        </p>
        <div class="verification__row">
            <label for="verification-applicant-id">{{ t('local.applicantId') }}</label>
            <input id="verification-applicant-id" v-model="applicantId" class="verification__input" type="number" min="1">
            <BaseButton size="small" :disabled="busy || !validId(applicantId)" @click="approve">
                {{ t('local.approve') }}
            </BaseButton>
            <BaseButton size="small" :disabled="busy || !validId(applicantId)" @click="reject">
                {{ t('local.reject') }}
            </BaseButton>
        </div>
        <div v-if="status?.has_relation" class="verification__row">
            <BaseButton size="small" type="danger" :disabled="busy" @click="detach">
                {{ t('local.detach') }}
            </BaseButton>
            <span class="text-regular text-small">{{ t('local.detachHint') }}</span>
        </div>
        <p v-if="taskMessage" class="text-regular text-small" role="status" data-cy="verification-task">
            {{ taskMessage }}
        </p>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { generalErrorNotification, httpErrorNotification } from '@/components/Notifications';
import $axios from '@/http';
import { applyLoginSession } from '@/services/loginSession';
import {
    approveVerificationRequest, createVerificationRequest, detachVerification, fetchVerificationStatus,
    fetchVerificationTask, rejectVerificationRequest,
} from '@/services/playerVerificationService';
import type { VerificationStatus, VerificationTaskAccepted } from '@/services/playerVerificationService';
import { invalidateUserInfo } from '@/services/userService';
import type { UserProfileData } from '@/utils/userprofile';

const props = defineProps({
    userId: { type: Number, required: true },
});
const emit = defineEmits<{
    changed: [];
}>();

const status = ref<VerificationStatus | null>(null);
const busy = ref(false);
const taskMessage = ref('');
const requestUserId = ref<number | string>('');
const applicantId = ref<number | string>('');
let pollTimer: ReturnType<typeof setInterval> | undefined;
let polling = false;
let unmounted = false;

function validId(value: number | string): boolean {
    const id = Number(value);
    return Number.isInteger(id) && id > 0;
}

function toId(value: number | string): number {
    return Number(value);
}

const requestDescription = computed(() => {
    const current = status.value;
    if (current === null) return '';
    switch (current.request_state) {
        case 'none':
            return t('local.stateNone');
        case 'pending':
            return t('local.statePending', { id: current.request_parent_id ?? '' });
        case 'expired':
            return t('local.stateExpired');
        case 'rejected':
            return t('local.stateRejected', { time: displayTime(current.cooldown_until) });
        case 'approved':
            return t('local.stateApproved');
        case 'verified_root':
            return t('local.stateVerifiedRoot');
        default:
            return t('local.stateUnverifiedRoot');
    }
});

function displayTime(value: string | null): string {
    if (value === null) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
}

function showError(error: unknown): void {
    if (isAxiosError<{ object?: string; category?: string }>(error) && error.response?.data?.object === 'verification') {
        generalErrorNotification('verification', error.response.data.category ?? 'not_found');
    } else {
        httpErrorNotification(error);
    }
}

function stopPolling(): void {
    if (pollTimer !== undefined) clearInterval(pollTimer);
    pollTimer = undefined;
}

async function refreshSelf(): Promise<void> {
    await invalidateUserInfo(props.userId);
    const { data } = await $axios.get<{ user: UserProfileData | null }>('/api/common/loginauto', { params: { _t: Date.now() } });
    if (data.user !== null) await applyLoginSession(data.user, $axios);
    emit('changed');
}

async function load(): Promise<void> {
    const current = await fetchVerificationStatus();
    status.value = current;
    if (!unmounted && current.processing_task_id !== null) startPolling(current.processing_task_id);
}

async function checkTask(id: string): Promise<void> {
    if (polling) return;
    polling = true;
    try {
        const result = await fetchVerificationTask(id);
        if (result.status === 'READY' || result.status === 'RUNNING') return;
        stopPolling();
        const applied = result.status === 'SUCCESSFUL' && result.result?.status === 'applied';
        taskMessage.value = applied ? t('local.taskDone') : t('local.taskConflict');
        await refreshSelf();
        if (!unmounted) await load();
    } catch (error) {
        stopPolling();
        taskMessage.value = t('errorMsg.verification.task_failed');
        showError(error);
    } finally {
        polling = false;
    }
}

function startPolling(id: string): void {
    stopPolling();
    if (unmounted) return;
    taskMessage.value = t('local.taskPending');
    pollTimer = setInterval(() => {
        void checkTask(id);
    }, 1000);
}

async function withBusy(action: () => Promise<void>): Promise<void> {
    busy.value = true;
    try {
        await action();
    } catch (error) {
        showError(error);
    } finally {
        busy.value = false;
    }
}

function acceptedTask(task: VerificationTaskAccepted): void {
    startPolling(task.task_id);
    void load().catch(showError);
}

function submitRequest(): void {
    if (!validId(requestUserId.value)) return;
    void withBusy(async () => {
        status.value = await createVerificationRequest(toId(requestUserId.value));
        requestUserId.value = '';
        await refreshSelf();
    });
}

function approve(): void {
    if (!validId(applicantId.value)) return;
    void withBusy(async () => {
        acceptedTask(await approveVerificationRequest(toId(applicantId.value)));
    });
}

function reject(): void {
    if (!validId(applicantId.value)) return;
    void withBusy(async () => {
        await rejectVerificationRequest(toId(applicantId.value));
        applicantId.value = '';
        await load();
    });
}

function detach(): void {
    void withBusy(async () => {
        acceptedTask(await detachVerification());
    });
}

onMounted(() => {
    void load().catch(showError);
});
onUnmounted(() => {
    unmounted = true;
    stopPolling();
});

const i18nMessages = {
    'zh-cn': { local: {
        title: '玩家认证',
        current: '当前状态',
        verified: '已认证',
        unverified: '未认证',
        access: '录像与比赛准入',
        allowed: '已开放',
        blocked: '未开放',
        hint: '完成实名或由已认证玩家认证后即可上传录像、报名比赛。实名或玩家认证任一项变化都会更新准入。',
        requestTo: '认证方本站 ID',
        applicantId: '申请人本站 ID',
        sendRequest: '发起申请',
        approve: '认证',
        reject: '拒绝',
        detach: '解除当前认证关系',
        detachHint: '解除后本站认证失效，已实名用户仍可继续上传与报名。',
        stateNone: '当前没有申请。',
        statePending: '已向用户 #{id} 发出申请，七天内等待对方处理；期间不能换人或撤回。',
        stateExpired: '上次申请已过期，可以发起新申请；发起时会替换旧记录。',
        stateRejected: '上次申请已被拒绝或已解除，冷却至 {time}。',
        stateApproved: '已有认证关系，可通过下方按钮解除。',
        stateVerifiedRoot: '已由管理员直接认证。',
        stateUnverifiedRoot: '当前未认证，可以重新发起申请。',
        taskPending: '认证任务排队或处理中，完成后自动刷新。',
        taskDone: '认证任务已完成。',
        taskConflict: '认证任务未生效：申请状态已变化，请刷新后重试。',
    } },
    en: { local: {
        title: 'Player verification',
        current: 'Status',
        verified: 'Verified',
        unverified: 'Not verified',
        access: 'Replay & tournament access',
        allowed: 'Granted',
        blocked: 'Blocked',
        hint: 'Verify your real name or get verified by a verified player to upload replays and enter tournaments. Either change updates access.',
        requestTo: 'Verifier user ID',
        applicantId: 'Applicant user ID',
        sendRequest: 'Send request',
        approve: 'Verify',
        reject: 'Reject',
        detach: 'Detach verification',
        detachHint: 'Site verification is lost. A real-name user can still upload and register.',
        stateNone: 'There is no request.',
        statePending: 'A request was sent to user #{id}. It stays open for seven days and cannot be withdrawn or redirected.',
        stateExpired: 'The previous request expired. Sending a new one replaces it.',
        stateRejected: 'The previous request was rejected or detached. Cooldown ends at {time}.',
        stateApproved: 'An established verification relation exists. Detach it below.',
        stateVerifiedRoot: 'Verified directly by an administrator.',
        stateUnverifiedRoot: 'Not verified. You may send a new request.',
        taskPending: 'The verification task is queued or running. This page refreshes when it finishes.',
        taskDone: 'The verification task completed.',
        taskConflict: 'The verification task did not apply: the request changed. Refresh and try again.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.verification__status,
.verification__row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.4rem;
}

.verification__input {
    width: 8rem;
    padding: 0.15rem 0.35rem;
    border: 1px solid var(--el-border-color);
    border-radius: 0;
    background: var(--el-bg-color);
    color: var(--el-text-color-primary);
}
</style>
