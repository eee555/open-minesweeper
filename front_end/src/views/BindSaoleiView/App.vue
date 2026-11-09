<template>
    <div class="bind-saolei layout-stack">
        <section class="card">
            <h2 class="card-title">
                {{ t('local.title') }}
            </h2>

            <p v-if="state === 'loading'" class="bind-hint text-secondary text-small">
                {{ t('local.loading') }}
            </p>

            <template v-else-if="state === 'ready' && request">
                <p class="bind-intro">
                    <PlatformIcon platform="c" /> {{ t('local.intro1') }}
                    <b>{{ request.username }} (ID {{ request.uid }})</b>{{ t('local.intro2') }}
                </p>
                <label class="bind-toggle checkbox">
                    <input v-model="sync" class="checkbox-input" type="checkbox">
                    <span>{{ t('local.toggle') }}</span>
                </label>
                <p class="bind-hint text-secondary text-small">
                    {{ t('local.toggleHint') }}
                </p>
                <BaseButton type="primary" :disabled="sending" :loading="sending" @click="confirm">
                    {{ t('local.confirm') }}
                </BaseButton>
                <p v-if="errorMessage" class="text-danger" role="alert">
                    {{ errorMessage }}
                </p>
            </template>

            <p v-else-if="state === 'loginRequired'" class="bind-hint text-secondary text-small">
                {{ t('local.loginRequired') }}
            </p>

            <p v-else-if="state === 'invalid'" class="bind-hint text-secondary text-small">
                {{ errorMessage || t('local.invalid') }}
            </p>

            <p v-else-if="state === 'done'" class="bind-done text-success">
                {{ t('local.done') }}
            </p>
        </section>

        <section class="card">
            <h3 class="bind-subtitle">
                {{ t('local.guideTitle') }}
            </h3>
            <p class="bind-hint text-secondary text-small">
                {{ t('local.guide1') }}
            </p>
            <p class="bind-hint text-secondary text-small">
                {{ t('local.guide2') }}
            </p>
        </section>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/layout.css';
import { onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import PlatformIcon from '@/components/widgets/PlatformIcon.vue';
import { confirmSaoleiBind, fetchSaoleiBindRequest, isSaoleiBindToken } from '@/services/saoleiBindService';
import type { SaoleiBindErrorCategory, SaoleiBindRequestInfo } from '@/services/saoleiBindService';

const route = useRoute();
const state = ref<'loading' | 'ready' | 'loginRequired' | 'invalid' | 'done'>('loading');
const request = ref<SaoleiBindRequestInfo | null>(null);
const sync = ref(true); // 「扫雷网录像自动同步到本站」默认勾选（2026-11-09 与扫雷网对齐：开关默认开启，可随时调整）
const sending = ref(false);
const errorMessage = ref('');
const token = ref('');
let revision = 0;

async function load() {
    const current = ++revision;
    state.value = 'loading';
    request.value = null;
    sync.value = true;
    sending.value = false;
    errorMessage.value = '';
    token.value = '';
    const tokenParam = route.query.token;
    const tokenValue = typeof tokenParam === 'string' ? tokenParam : undefined;
    if (!isSaoleiBindToken(tokenValue)) {
        state.value = 'invalid';
        return;
    }
    token.value = tokenValue;
    try {
        const info = await fetchSaoleiBindRequest(token.value);
        if (current !== revision) return;
        if (info.status !== 0) {
            state.value = 'invalid';
            return;
        }
        request.value = info;
        state.value = 'ready';
    } catch (error) {
        if (current !== revision) return;
        const { category } = error as { category?: SaoleiBindErrorCategory };
        if (category === 'login_required') {
            state.value = 'loginRequired';
        } else {
            state.value = 'invalid';
            errorMessage.value = category === 'invalid_token' ? t('local.invalidToken') : t('local.networkError');
        }
    }
}

async function confirm() {
    if (sending.value || !request.value) return;
    const current = revision;
    sending.value = true;
    errorMessage.value = '';
    try {
        await confirmSaoleiBind(token.value, sync.value);
        if (current !== revision) return;
        state.value = 'done';
    } catch (error) {
        if (current !== revision) return;
        const { category } = error as { category?: SaoleiBindErrorCategory };
        errorMessage.value = t(`local.error.${category ?? 'network'}`);
        if (category === 'invalid_token') {
            state.value = 'invalid';
        }
    }
    if (current === revision) sending.value = false;
}

onBeforeUnmount(() => {
    revision++;
});

const i18nMessages = {
    'zh-cn': { local: {
        title: '绑定扫雷网',
        loading: '正在读取绑定申请…',
        intro1: '扫雷网用户 ',
        intro2: ' 申请与您的开源扫雷网账户绑定。请核对上方用户名后确认。',
        toggle: '扫雷网录像自动同步到本站',
        toggleHint: '默认勾选；取消勾选则不同步，绑定后可随时在「绑定账户」页调整。',
        confirm: '确认绑定',
        done: '绑定成功！本站将按您的同步设置导入扫雷网录像。',
        loginRequired: '请先登录开源扫雷网账户（右上角菜单 → 登录），登录后刷新本页继续。',
        invalid: '绑定申请不存在或已失效，请在扫雷网重新发起绑定。',
        invalidToken: '绑定申请不存在或已失效，请在扫雷网重新发起绑定。',
        networkError: '网络异常，请刷新重试。',
        guideTitle: '关于扫雷网绑定',
        guide1: '绑定后，您的扫雷网历史与新录像可按同步设置自动导入本站。',
        guide2: '扫雷网侧的同步开关在其授权页设置；两边各自控制自己方向的同步。',
        error: {
            login_required: '请先登录开源扫雷网账户，登录后刷新本页重试。',
            invalid_token: '绑定申请不存在或已失效，请在扫雷网重新发起绑定。',
            collision: '该扫雷网账户已被其他开源扫雷网用户绑定。',
            network: '网络异常，请重试。',
        },
    } },
    en: { local: {
        title: 'Link Saolei.wang',
        loading: 'Loading the link request…',
        intro1: 'Saolei.wang user ',
        intro2: ' requests to link with your OpenMS account. Please verify the name above and confirm.',
        toggle: 'Automatically sync my Saolei.wang videos to OpenMS',
        toggleHint: 'Enabled by default; untick to skip. You can change it anytime on the Account Links page after linking.',
        confirm: 'Confirm',
        done: 'Linked! OpenMS will import your Saolei.wang videos according to your sync settings.',
        loginRequired: 'Please log in to OpenMS first (top-right menu → Log in), then refresh this page.',
        invalid: 'The link request does not exist or has expired. Please start again from Saolei.wang.',
        invalidToken: 'The link request does not exist or has expired. Please start again from Saolei.wang.',
        networkError: 'Network error, please refresh and retry.',
        guideTitle: 'About the Saolei.wang link',
        guide1: 'After linking, your Saolei.wang replays (history and new uploads) can be imported to OpenMS per your sync settings.',
        guide2: 'The sync toggle for the Saolei.wang side lives on its authorization page; each site controls its own direction.',
        error: {
            login_required: 'Please log in to OpenMS first, then refresh this page.',
            invalid_token: 'The link request does not exist or has expired. Please start again from Saolei.wang.',
            collision: 'This Saolei.wang account is already linked to another OpenMS user.',
            network: 'Network error, please retry.',
        },
    } },
};

const { t } = useI18n({ messages: i18nMessages });

watch(() => route.query.token, load, { immediate: true });
</script>

<style scoped>
.bind-saolei {
    max-width: 40rem;
    margin: 0 auto;
}

.bind-intro {
    margin: 0.5rem 0 1rem;
    word-break: break-word;
}

.bind-toggle {
    margin: 0.75rem 0;
}

.bind-hint {
    margin: 0.25rem 0 0.75rem;
}

.bind-subtitle {
    margin: 0 0 0.5rem;
    font-size: 1rem;
}

.bind-done {
    margin: 0.75rem 0 0;
}
</style>
