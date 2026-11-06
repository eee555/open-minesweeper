<template>
    <div class="account-panel">
        <div class="classic-link">
            <template v-if="showForm">
                <div class="classic-form">
                    <input v-model="uid" class="account-input" type="text" maxlength="8" :placeholder="t('local.uidPlaceholder')" @keyup.enter="submit">
                    <BaseButton type="primary" :disabled="!uidValid" :loading="startLoading" @click="submit">
                        {{ t('local.request') }}
                    </BaseButton>
                </div>
                <details>
                    <summary>{{ t('local.qrCode') }}</summary>
                    <img class="classic-qrcode" src="@/assets/classic95link.jpg" :alt="t('local.qrCode')">
                </details>
                <details class="classic-guide">
                    <summary>{{ t('local.title') }}</summary>
                    {{ t('local.howTo') }}
                    <img src="@/assets/IdGuide95Classic.png" :alt="t('local.title')">
                </details>
            </template>

            <template v-else>
                <div class="description-layout">
                    <dl class="descriptions descriptions-bordered">
                        <div class="description-item">
                            <dt>{{ t('local.uid') }}</dt><dd>
                                {{ link.uid }}
                            </dd>
                        </div>
                        <div v-if="link.status === 'pending'" class="description-item">
                            <dt>{{ t('local.expiresIn') }}</dt><dd>
                                {{ remainingTimeText }}
                            </dd>
                        </div>
                    </dl>
                </div>

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

            <p v-if="messageKey" role="status" :class="messageType === 'success' ? 'text-success' : 'text-danger'">
                {{ t(`local.msg.${messageKey}`) }}
            </p>
        </div>
    </div>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '../page.css';
import { computed } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { useClassicLink } from './useClassicLink';

import BaseButton from '@/components/common/BaseButton.vue';
import { BaseIconRefresh } from '@/components/common/icon';
import { globalNow } from '@/utils/datetime';

const props = defineProps({ flow: { type: Object as PropType<ReturnType<typeof useClassicLink>>, required: true } });
const { link, uid, startLoading, statusLoading, httpErrorMessageKey, refreshStatus, submit } = props.flow;
const uidValid = computed(() => (/^[1-9]\d{7}$/).test(uid.value));
const showForm = computed(() => !['pending', 'allow'].includes(link.value.status));
const remainingTimeText = computed(() => {
    const seconds = Math.max(0, Math.ceil(((link.value.expires_at?.getTime() ?? 0) - globalNow.value.getTime()) / 1000));
    return Math.floor(seconds / 3600) + ':' + Math.floor(seconds % 3600 / 60).toString().padStart(2, '0');
});
const statusMessageKeys: Record<string, string> = { conflict: 'conflict', deny: 'denied', expired: 'expired', revoke: 'revoked' };
const messageKey = computed(() => httpErrorMessageKey.value || (link.value.status === 'allow' ? 'linkSuccess' : ['pending', 'none'].includes(link.value.status) ? '' : link.value.error_category || statusMessageKeys[link.value.status]));
const messageType = computed(() => (link.value.status === 'allow' ? 'success' : 'error'));

const i18nMessages = {
    'zh-cn': { local: {
        howTo: '在「95经典扫雷」小游戏里打开「我的荣誉」，点击右上角的 UID 即可复制，粘贴到上方输入框提交。提交后回到小游戏内确认绑定。',
        qrCode: '95经典扫雷小游戏二维码',
        title: '如何找到ID',
        expiresIn: '剩余时间',
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
        uid: '95 经典扫雷 UID',
        uidPlaceholder: '8 位 UID',
        waiting: '请在小游戏内点击确认，确认后本页会自动更新。',
    } },
    en: { local: {
        howTo: 'Open “My Honours” in the 95 Classic Minesweeper mini game, tap the UID at the top right to copy it, then paste it into the field above. Confirm the request inside the game afterwards.',
        qrCode: 'QR code for the 95 Classic Minesweeper mini game',
        title: 'How to locate the ID',
        expiresIn: 'Expires in',
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
        border-radius: 0;
        display: block;
        width: 100%;
        max-width: 500px;
        height: auto;
        margin-top: 0.5rem;
    }
}

.classic-qrcode {
    display: block;
    width: 100%;
    max-width: 300px;
    height: auto;
    margin-top: 0.5rem;
}

.classic-actions {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}
</style>
