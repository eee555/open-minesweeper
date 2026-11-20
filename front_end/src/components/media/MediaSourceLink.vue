<template>
    <span class="media-source">
        <a v-if="url" v-bind="$attrs" class="link" :href="url" target="_blank" rel="noopener noreferrer"><slot /></a>
        <button v-else-if="format === 'g_r'" v-bind="$attrs" type="button" class="link media-text-button" :disabled="loading" :aria-busy="loading" @click="resolve">
            <slot /><span v-if="loading"> · {{ t('local.loading') }}</span>
        </button>
        <span v-else v-bind="$attrs"><slot /></span>
        <span v-if="failed" class="text-danger text-small" role="alert"> {{ t('local.failed') }}</span>
    </span>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { fetchGitHubRepositoryUrl } from '@/services/githubService';
import { mediaExternalUrl } from '@/utils/media';

const props = defineProps({ format: { type: String, required: true }, suffix: { type: String, required: true } });
defineOptions({ inheritAttrs: false });
defineSlots<{ default?: () => unknown }>();
const resolved = ref<string>();
const loading = ref(false);
const failed = ref(false);
const url = computed(() => mediaExternalUrl(props.format, props.suffix) ?? resolved.value);
let controller: AbortController | undefined;
let popup: Window | null = null;

function cancel(): void {
    controller?.abort();
    popup?.close(); popup = null;
    resolved.value = undefined; loading.value = false; failed.value = false;
}
watch(() => [props.format, props.suffix], cancel);
onScopeDispose(cancel);

async function resolve(): Promise<void> {
    if (loading.value) return;
    const request = new AbortController();
    controller = request;
    loading.value = true; failed.value = false;
    let opened: Window | null = null;
    try {
        // 在用户手势内打开空窗口；异步完成后再导航，避免浏览器拦截弹窗。
        opened = window.open('about:blank', '_blank');
        popup = opened;
        if (opened) {
            opened.opener = null;
            const policy = opened.document.createElement('meta');
            policy.name = 'referrer'; policy.content = 'no-referrer';
            opened.document.head.append(policy);
        }
        const target = await fetchGitHubRepositoryUrl(props.suffix, AbortSignal.any([request.signal, AbortSignal.timeout(10000)]));
        if (request.signal.aborted) return;
        resolved.value = target;
        popup = null;
        if (opened && !opened.closed) opened.location.replace(target);
        // 弹窗被拦截时仍显示真实外链，用户可再次点击或复制地址。
    } catch {
        opened?.close();
        if (!request.signal.aborted) failed.value = true;
    } finally {
        if (controller === request) {
            popup = null; loading.value = false;
        }
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        loading: '获取仓库地址中',
        failed: '获取失败，请再次点击重试。',
    } },
    en: { local: {
        loading: 'Loading repository link',
        failed: 'Could not load the link. Click again to retry.',
    } },
    es: { local: {
        loading: 'Cargando el enlace al repositorio',
        failed: 'No se pudo cargar el enlace. Haz clic para reintentar.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
