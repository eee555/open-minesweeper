<template>
    <BaseCardNormal>
        <div class="classic-link">
            <PrToolbar>
                <template #start>
                    <span class="text-medium text-regular">
                        {{ t('platform.x') }}
                    </span>
                </template>
                <template v-if="link.status !== 'none'" #end>
                    <ElTag :type="statusTagType">
                        {{ t(`local.status.${link.status}`) }}
                    </ElTag>
                </template>
            </PrToolbar>

            <template v-if="showForm">
                <div class="classic-guide">
                    <b>{{ t('local.title') }}</b><br>
                    {{ t('local.howTo') }}
                    <img src="../../assets/IdGuide95Classic.png" :alt="t('local.title')" width="100%">
                </div>
                <div class="classic-form">
                    <ElInput v-model="uid" maxlength="8" :placeholder="t('local.uidPlaceholder')" @keyup.enter="submit" />
                    <BaseButton type="primary" :disabled="!uidValid" :loading="startLoading" @click="submit">
                        {{ t('local.request') }}
                    </BaseButton>
                </div>
            </template>

            <template v-else>
                <ElDescriptions border :column="1" size="small">
                    <ElDescriptionsItem :label="t('local.uid')">
                        {{ link.uid }}
                    </ElDescriptionsItem>
                    <ElDescriptionsItem v-if="link.status === 'pending'" :label="t('local.expiresIn')">
                        {{ remainingTimeText }}
                    </ElDescriptionsItem>
                </ElDescriptions>

                <div v-if="link.status === 'pending'" class="classic-actions">
                    <span class="text-regular">{{ t('local.waiting') }}</span>
                    <BaseButton text :loading="statusLoading" @click="refreshStatus">
                        <template #icon>
                            <BaseIconRefresh />
                        </template>
                        {{ t('local.refreshStatus') }}
                    </BaseButton>
                </div>
            </template>

            <ElAlert v-if="messageKey" :title="t(`local.msg.${messageKey}`)" :type="messageType" show-icon :closable="false" />
        </div>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElAlert, ElDescriptions, ElDescriptionsItem, ElInput, ElTag } from 'element-plus';
import PrToolbar from 'primevue/toolbar';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import { httpErrorNotification } from '@/components/Notifications';
import { fetchClassicAccountLink, getClassicAccountLinkHttpErrorCategory, startClassicAccountLink } from '@/services/classicService';
import { ClassicAccountLink } from '@/utils/accountlinks';
import { globalNow } from '@/utils/datetime';

const emit = defineEmits<{
    refresh: [];
}>();

const CLASSIC_POLL_INTERVAL_MS = 5000;
const statusMessageKeys: Record<string, string> = { conflict: 'conflict', deny: 'denied', expired: 'expired', revoke: 'revoked' };

const link = ref(new ClassicAccountLink());
const uid = ref('');
const startLoading = ref(false);
const statusLoading = ref(false);
const httpErrorMessageKey = ref('');
let pollTimer: number | undefined;
let unmounted = false;

const uidValid = computed(() => (/^[1-9]\d{7}$/).test(uid.value));
const showForm = computed(() => !['pending', 'allow'].includes(link.value.status));
const statusTagType = computed(() => {
    if (link.value.status === 'allow') return 'success';
    if (link.value.status === 'pending') return 'warning';
    return 'info';
});
const remainingTimeText = computed(() => formatRemainingTime((link.value.expires_at?.getTime() ?? 0) - globalNow.value.getTime()));
const messageKey = computed(() => {
    if (httpErrorMessageKey.value) return httpErrorMessageKey.value;
    if (link.value.status === 'pending' || link.value.status === 'none') return '';
    if (link.value.status === 'allow') return 'linkSuccess';
    if (link.value.error_category) return link.value.error_category;
    return statusMessageKeys[link.value.status];
});
const messageType = computed(() => (link.value.status === 'allow' ? 'success' : 'error'));

function applyLink(nextLink: ClassicAccountLink) {
    // 卸载后到达的响应不能再改状态，也不能重启轮询。
    if (unmounted) return;
    link.value = nextLink;
    if (nextLink.status === 'pending') {
        schedulePoll();
    } else {
        clearPollTimer();
    }
    if (nextLink.status === 'allow') emit('refresh');
}

async function loadStatus() {
    statusLoading.value = true;
    try {
        applyLink(await fetchClassicAccountLink());
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        statusLoading.value = false;
    }
}

async function refreshStatus() {
    httpErrorMessageKey.value = '';
    await loadStatus();
}

async function submit() {
    if (!uidValid.value) return;
    httpErrorMessageKey.value = '';
    startLoading.value = true;
    try {
        applyLink(await startClassicAccountLink(uid.value));
    } catch (error) {
        const category = getClassicAccountLinkHttpErrorCategory(error);
        if (category === undefined) {
            httpErrorNotification(error);
        } else {
            httpErrorMessageKey.value = category;
        }
    } finally {
        startLoading.value = false;
    }
}

function schedulePoll() {
    clearPollTimer();
    pollTimer = window.setTimeout(() => {
        void refreshStatus();
    }, CLASSIC_POLL_INTERVAL_MS);
}

function clearPollTimer() {
    if (pollTimer === undefined) return;
    window.clearTimeout(pollTimer);
    pollTimer = undefined;
}

function formatRemainingTime(milliseconds: number): string {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    return `${hours}:${minutes.toString().padStart(2, '0')}`;
}

onMounted(() => {
    void loadStatus();
});
onBeforeUnmount(() => {
    unmounted = true;
    clearPollTimer();
});

const i18nMessages = {
    'zh-cn': { local: {
        expiresIn: '剩余时间',
        howTo: '在「95经典扫雷」小游戏里打开「我的荣誉」，点击右上角的 UID 即可复制，粘贴到下方提交。提交后回到小游戏内确认绑定。',
        msg: {
            already_bound: '该账号已经绑定过本应用。',
            already_linked: '已经关联了 95 经典扫雷账号。',
            app_mismatch: '绑定接口的应用配置不一致，请联系管理员。',
            bad_callback: '回调地址未通过对方校验，请联系管理员。',
            bad_request: 'UID 格式不正确，应为 8 位数字。',
            conflict: '该账号已被其他用户绑定，请联系管理员。',
            denied: '玩家拒绝了本次绑定申请，1 小时内无法再次申请。',
            denied_recently: '该玩家在 1 小时内拒绝过本应用的绑定申请，请稍后再试。',
            expired: '申请已过期，请重新提交。',
            identifier_conflict: '该 UID 已被其他用户绑定。',
            linkSuccess: '95 经典扫雷账号关联成功。',
            not_configured: '95 经典扫雷关联尚未配置。',
            pending: '该 UID 有尚未处理的申请，请稍后再试。',
            rate_limited: '申请过于频繁，请稍后再试。',
            requestexception: '请求 95 经典扫雷失败。',
            response: '95 经典扫雷返回了无法识别的响应。',
            revoked: '玩家已在小游戏内解除绑定，请重新提交申请。',
            revoked_recently: '该玩家在 1 小时内解绑过本应用，请稍后再试。',
            timeout: '95 经典扫雷响应超时。',
            uid_not_found: '该 UID 不存在，请确认玩家已进入过小游戏。',
            unauthorized: '绑定接口凭证无效，请联系管理员。',
        },
        refreshStatus: '刷新状态',
        request: '提交申请',
        status: {
            allow: '已关联',
            conflict: '关联冲突',
            deny: '已拒绝',
            expired: '已过期',
            none: '未申请',
            pending: '等待小游戏确认',
            revoke: '已解绑',
        },
        title: '如何找到ID',
        uid: '95 经典扫雷 UID',
        uidPlaceholder: '8 位 UID',
        waiting: '请在小游戏内点击确认，确认后本页会自动更新。',
    } },
    en: { local: {
        expiresIn: 'Expires in',
        howTo: 'Open “My Honours” in the 95 Classic Minesweeper mini game, tap the UID at the top right to copy it, then paste it below. Confirm the request inside the game afterwards.',
        msg: {
            already_bound: 'This account is already bound to the app.',
            already_linked: 'A 95 Classic Minesweeper account is already linked.',
            app_mismatch: 'The binding app configuration does not match. Please contact the administrator.',
            bad_callback: 'The callback address was rejected by the remote side. Please contact the administrator.',
            bad_request: 'The UID must be an 8-digit number.',
            conflict: 'This account is already bound to another user. Please contact the administrator.',
            denied: 'The player denied this request. A new request is blocked for 1 hour.',
            denied_recently: 'The player denied a request from this app in the last hour. Please try again later.',
            expired: 'The request expired. Please submit it again.',
            identifier_conflict: 'This UID is already linked to another user.',
            linkSuccess: '95 Classic Minesweeper account linked.',
            not_configured: '95 Classic Minesweeper linking is not configured.',
            pending: 'This UID already has a pending request. Please try again later.',
            rate_limited: 'Too many requests. Please try again later.',
            requestexception: 'Failed to reach 95 Classic Minesweeper.',
            response: '95 Classic Minesweeper returned an unrecognised response.',
            revoked: 'The player unlinked this app in the mini game. Please submit a new request.',
            revoked_recently: 'The player unbound this app in the last hour. Please try again later.',
            timeout: '95 Classic Minesweeper did not respond in time.',
            uid_not_found: 'This UID does not exist. Ask the player to open the mini game first.',
            unauthorized: 'The binding credentials are invalid. Please contact the administrator.',
        },
        refreshStatus: 'Refresh status',
        request: 'Send request',
        status: {
            allow: 'Linked',
            conflict: 'Conflict',
            deny: 'Denied',
            expired: 'Expired',
            none: 'Not requested',
            pending: 'Waiting for confirmation',
            revoke: 'Unlinked',
        },
        title: 'How to locate the ID',
        uid: '95 Classic Minesweeper UID',
        uidPlaceholder: '8-digit UID',
        waiting: 'Confirm the request inside the mini game. This page updates automatically.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.classic-link {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 0;
}

.classic-form {
    display: flex;
    gap: 0.5rem;
}

.classic-guide {
    line-height: 1.5;

    img {
        border-radius: 0.25rem;
        display: block;
        margin-top: 0.5rem;
    }
}

.classic-actions {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}
</style>
