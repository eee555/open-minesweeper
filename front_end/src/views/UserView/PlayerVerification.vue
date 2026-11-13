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
            <span>{{ t('local.access') }}{{ t('punct.colon') }}{{ store.canSubmitReplays ? t('local.allowed') : t('local.blocked') }}</span>
        </div>
        <p class="text-regular text-small">
            {{ t('local.hint') }}
        </p>
        <div class="verification__row">
            <label for="verification-target-id">{{ t('local.targetId') }}</label>
            <input id="verification-target-id" v-model="targetId" class="verification__input" type="number" min="1">
            <BaseButton size="small" :disabled="busy || !status?.can_verify || status?.maintenance_active || !validId(targetId)" @click="submitVerification">
                {{ t('local.verify') }}
            </BaseButton>
        </div>
        <p v-if="status?.maintenance_active" class="text-regular text-small text-warning" data-cy="verification-maintenance">
            {{ t('local.maintenance') }}
        </p>
        <p v-if="message" class="text-regular text-small" role="status" data-cy="verification-result">
            {{ message }}
        </p>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { generalErrorNotification, httpErrorNotification } from '@/components/Notifications';
import { applySelfVerification } from '@/services/loginSession';
import { fetchVerificationStatus, verifyPlayer } from '@/services/playerVerificationService';
import type { VerificationStatus } from '@/services/playerVerificationService';
import { store } from '@/store';

const props = defineProps({
    userId: { type: Number, required: true },
});

const status = ref<VerificationStatus | null>(null);
const busy = ref(false);
const message = ref('');
const targetId = ref<number | string>('');

function validId(value: number | string): boolean {
    const id = Number(value);
    return Number.isInteger(id) && id > 0;
}

function showError(error: unknown): void {
    if (isAxiosError<{ object?: string; category?: string }>(error) && error.response?.data?.object === 'verification') {
        generalErrorNotification('verification', error.response.data.category ?? 'not_found');
    } else {
        httpErrorNotification(error);
    }
}

async function load(): Promise<void> {
    const { userId } = props;
    const revision = store.sessionRevision;
    const current = await fetchVerificationStatus();
    // 刷新期间若已切换到其他账号，不把旧账号的状态写回这个页面。
    if (props.userId !== userId || !applySelfVerification(userId, revision, current.verified)) return;
    status.value = current;
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

function submitVerification(): void {
    if (!validId(targetId.value)) return;
    void withBusy(async () => {
        const result = await verifyPlayer(Number(targetId.value));
        message.value = result.edge_created ? t('local.verifyDone') : t('local.verifyDuplicate');
        targetId.value = '';
        await load();
    });
}

onMounted(() => {
    void load().catch(showError);
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
        hint: '完成实名或由已认证玩家认证后即可上传录像、报名比赛。已认证玩家可输入对方本站 ID 直接认证，无需对方申请；认证不可自行撤回。',
        targetId: '对方本站 ID',
        verify: '认证该用户',
        maintenance: '站长正在维护认证关系，暂时不能发起认证。',
        verifyDone: '已认证该用户。',
        verifyDuplicate: '你已认证过该用户，无需重复操作。',
    } },
    en: { local: {
        title: 'Player verification',
        current: 'Status',
        verified: 'Verified',
        unverified: 'Not verified',
        access: 'Replay & tournament access',
        allowed: 'Granted',
        blocked: 'Blocked',
        hint: 'Complete real-name verification or be verified by a verified player to upload replays and enter tournaments. Verified players can verify another user by site ID; no request, approval or self-detach exists.',
        targetId: 'Target user ID',
        verify: 'Verify user',
        maintenance: 'A superuser is maintaining verification relations. New verifications are paused.',
        verifyDone: 'The user is now verified.',
        verifyDuplicate: 'You have already verified this user.',
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
