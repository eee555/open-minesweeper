<template>
    <span class="media-source">
        <a v-if="url" v-bind="$attrs" class="link" :href="url" :title="tooltip" target="_blank" rel="noopener noreferrer"><template v-if="detailLabel">{{ detailLabel }}</template><slot v-else /></a>
        <button v-else-if="format === 'g_r'" v-bind="$attrs" type="button" class="link media-text-button" :title="tooltip" :disabled="loading" :aria-busy="loading" @click="resolve">
            <template v-if="detailLabel">{{ detailLabel }}</template><slot v-else /><span v-if="loading"> · {{ t('local.loading') }}</span>
        </button>
        <span v-else v-bind="$attrs" :title="tooltip"><template v-if="detailLabel">{{ detailLabel }}</template><slot v-else /></span>
        <span v-if="failed" class="text-danger text-small" role="alert"> {{ t('local.failed') }}</span>
    </span>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, ref, useAttrs, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { fetchGitHubRepositoryInfo } from '@/services/githubService';
import type { GitHubRepositoryInfo } from '@/services/githubService';
import { mediaExternalUrl } from '@/utils/media';

const props = defineProps({ format: { type: String, required: true }, suffix: { type: String, required: true }, showGithubDetail: { type: Boolean, default: false } });
defineOptions({ inheritAttrs: false });
defineSlots<{ default?: () => unknown }>();
const resolved = ref<string>();
const repositoryInfo = ref<GitHubRepositoryInfo>();
const loading = ref(false);
const failed = ref(false);
const url = computed(() => mediaExternalUrl(props.format, props.suffix) ?? resolved.value);
const detailLabel = computed(() => {
    if (!props.showGithubDetail || props.format !== 'g_r' || !repositoryInfo.value) return undefined;
    const { fullName, description } = repositoryInfo.value;
    return description ? `${fullName}: ${description}` : fullName;
});
const attrs = useAttrs();
const tooltip = computed(() => detailLabel.value ?? (typeof attrs.title === 'string' ? attrs.title : undefined));
let controller: AbortController | undefined;
let detailController: AbortController | undefined;
let popup: Window | null = null;

function cancel(): void {
    controller?.abort();
    detailController?.abort();
    popup?.close(); popup = null;
    resolved.value = undefined; repositoryInfo.value = undefined; loading.value = false; failed.value = false;
}

async function loadDetail(): Promise<void> {
    if (!props.showGithubDetail || props.format !== 'g_r') return;
    const request = new AbortController();
    detailController = request;
    try {
        const info = await fetchGitHubRepositoryInfo(props.suffix, AbortSignal.any([request.signal, AbortSignal.timeout(10000)]));
        if (request.signal.aborted) return;
        repositoryInfo.value = info;
        resolved.value = info.htmlUrl;
    } catch {
        // 详情获取失败时保留上级提供的标题和点击解析行为。
    } finally {
        if (detailController === request) detailController = undefined;
    }
}

watch(() => [props.format, props.suffix, props.showGithubDetail], () => {
    cancel();
    void loadDetail();
}, { immediate: true });
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
        const info = await fetchGitHubRepositoryInfo(props.suffix, AbortSignal.any([request.signal, AbortSignal.timeout(10000)]));
        if (request.signal.aborted) return;
        repositoryInfo.value = info;
        resolved.value = info.htmlUrl;
        popup = null;
        if (opened && !opened.closed) opened.location.replace(info.htmlUrl);
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
