<template>
    <section ref="panel" class="media-panel">
        <form class="media-filters" @submit.prevent="applyFilters">
            <label>
                {{ t('local.type') }}
                <select v-model="draftFormat" data-cy="works-format">
                    <option value="">{{ t('local.allTypes') }}</option>
                    <option value="B_v">{{ t('local.bilibiliVideo') }}</option>
                    <option value="B_a">{{ t('local.bilibiliArticle') }}</option>
                    <option value="c_p">{{ t('local.saoleiPost') }}</option>
                    <option value="g_r">{{ t('local.githubRepository') }}</option>
                </select>
            </label>
            <label>
                {{ t('media.language') }}
                <ElSelect v-model="draftLanguage" clearable value-on-clear="" :placeholder="t('local.allLanguages')" data-cy="works-language">
                    <ElOption v-for="language in mediaLanguages" :key="language.lang" :value="language.lang" :label="language.text" />
                    <ElOption value="other" :label="t('local.otherLanguage')" />
                </ElSelect>
            </label>
            <BaseButton size="small" native-type="submit" data-cy="works-apply-filters">
                {{ t('local.apply') }}
            </BaseButton>
            <BaseTextButton data-cy="works-clear-filters" @click="clearFilters">
                {{ t('local.clear') }}
            </BaseTextButton>
        </form>
        <BaseTable
            table-class="media-works-table" :empty="items.length === 0" :column-count="5"
            :empty-text="loading ? t('local.loading') : t('media.empty')"
        >
            <template #head>
                <tr>
                    <th scope="col" class="media-col-title">
                        {{ t('media.title') }}
                    </th>
                    <th scope="col" class="table-col-player">
                        {{ t('media.author') }}
                    </th>
                    <th scope="col" class="table-col-datetime" :aria-sort="sort === 'latest' ? 'descending' : 'none'">
                        <BaseTextButton
                            :type="sort === 'latest' ? 'primary' : 'default'" :aria-pressed="sort === 'latest'"
                            data-sort="latest" @click="selectSort('latest')"
                        >
                            {{ t('media.publishedAt') }}
                        </BaseTextButton>
                    </th>
                    <th scope="col" class="table-col-number" :aria-sort="sort === 'hot' ? 'descending' : 'none'">
                        <BaseTextButton
                            :type="sort === 'hot' ? 'primary' : 'default'" :aria-pressed="sort === 'hot'"
                            data-sort="hot" @click="selectSort('hot')"
                        >
                            {{ t('media.hotNow') }}
                        </BaseTextButton>
                    </th>
                    <th scope="col" class="media-col-likes" :aria-sort="sort === 'likes' ? 'descending' : 'none'">
                        <BaseTextButton
                            :type="sort === 'likes' ? 'primary' : 'default'" :aria-pressed="sort === 'likes'"
                            data-sort="likes" @click="selectSort('likes')"
                        >
                            {{ t('media.likesCount') }}
                        </BaseTextButton>
                    </th>
                </tr>
            </template>
            <tr v-for="item in items" :key="item.id" :data-cy="`media-row-${item.id}`">
                <td class="media-col-title">
                    <span class="media-title-cell">
                        <span
                            v-if="platformIsMasked(item.format)" class="media-platform-icon media-platform-mask" data-cy="media-platform-icon"
                            role="img" :aria-label="platformName(item.format)" :title="platformName(item.format)"
                            :style="{ '--media-platform-mask': `url('${platformIconSrc(item.format)}')` }"
                        />
                        <img
                            v-else-if="platformIconSrc(item.format)" class="media-platform-icon" data-cy="media-platform-icon"
                            :src="platformIconSrc(item.format)" :alt="platformName(item.format)" :title="platformName(item.format)"
                        >
                        <button
                            v-if="mediaEmbedUrl(item.format, item.suffix)" type="button" class="link media-preview-link media-title-control"
                            data-cy="media-preview-link" :title="t('media.preview')" @click="openPreview(item)"
                        >
                            {{ item.title || t('media.titleMissing') }}
                        </button>
                        <MediaSourceLink v-else class="media-title-control" data-cy="media-title-link" show-github-detail :title="item.title || t('media.titleMissing')" :format="item.format" :suffix="item.suffix">{{ item.title || t('media.titleMissing') }}</MediaSourceLink>
                    </span>
                    <span v-if="item.metadata_pending" class="media-row-note text-secondary text-small">{{ t('media.titleMissing') }}</span>
                </td>
                <td class="table-col-player">
                    <PlayerName :user-id="item.user_id" />
                </td>
                <td class="table-col-datetime">
                    {{ formatDate(item.created_at) }}
                </td>
                <td class="table-col-number">
                    {{ formatHeat(item.hot_now) }}
                </td>
                <td class="media-col-likes">
                    <div class="media-likes-cell">
                        <span>{{ item.likes }}</span>
                        <MediaFeedButton
                            :media-id="item.id" :disabled="feedDisabled" :balance="me?.balance ?? null"
                            @feed="onFeed($event, item)"
                        />
                    </div>
                </td>
            </tr>
        </BaseTable>
        <div class="media-load-more" role="status" aria-live="polite">
            <span v-if="loading" class="text-secondary">{{ t('local.loading') }}</span>
            <template v-else-if="loadError">
                <span>{{ t('local.loadFailed') }}</span>
                <BaseTextButton data-cy="works-retry" @click="load">
                    {{ t('local.retry') }}
                </BaseTextButton>
            </template>
            <BaseTextButton v-else-if="hasMore" data-cy="works-load-more" @click="load">
                {{ t('local.loadMore') }}
            </BaseTextButton>
            <span v-else-if="items.length" class="text-secondary" data-cy="works-end">{{ t('local.end') }}</span>
        </div>
        <ElDialog v-if="preview" model-value :title="preview?.title || t('media.titleMissing')" width="min(720px, 95vw)" @close="preview = null">
            <iframe
                class="media-embed-frame media-preview-frame" :src="preview?.embedUrl"
                :title="preview?.title || t('media.titleMissing')" loading="lazy" referrerpolicy="no-referrer" allowfullscreen
            />
            <a class="link media-preview-external" :href="preview?.url" target="_blank" rel="noopener noreferrer">
                {{ t('media.openExternal') }}
            </a>
        </ElDialog>
    </section>
</template>

<script setup lang="ts">
import { useInfiniteScroll } from '@vueuse/core';
import { ElDialog, ElOption, ElSelect } from 'element-plus';
import { computed, onMounted, onScopeDispose, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import MediaFeedButton from './MediaFeedButton.vue';
import MediaSourceLink from './MediaSourceLink.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaFormatValue, MediaItem, MediaLikeResult, MediaMe, MediaWorksQuery, MediaWorksSort } from '@/services/mediaService';
import { fetchMediaMe, fetchMediaWorks } from '@/services/mediaService';
import { store } from '@/store';
import { AccountLinkPlatform } from '@/utils/accountlinks';
import { mediaEmbedUrl, mediaExternalUrl, mediaLanguages } from '@/utils/media';
import { platforms } from '@/views/UserView/AccountLinks/platforms';

import '@/components/media/media.css';

interface PreviewTarget { title: string; url: string; embedUrl: string }

const emit = defineEmits<{ loading: [value: boolean]; me: [value: MediaMe | null] }>();

// Media 的 format 首字符与 AccountLinkPlatform 一致；图标地址复用账号关联页的唯一来源。
const FORMAT_PLATFORM: Record<string, AccountLinkPlatform> = {
    B_v: AccountLinkPlatform.Bilibili,
    B_a: AccountLinkPlatform.Bilibili,
    c_p: AccountLinkPlatform.Saolei,
    g_r: AccountLinkPlatform.GitHub,
};

function platformEntry(format: string) {
    return platforms.find((entry) => entry.id === FORMAT_PLATFORM[format]);
}

function platformIconSrc(format: string): string {
    return platformEntry(format)?.src ?? '';
}

function platformIsMasked(format: string): boolean {
    return platformEntry(format)?.mask ?? false;
}

function platformName(format: string): string {
    return t(`platform.${FORMAT_PLATFORM[format]}`);
}

const sort = ref<MediaWorksSort>('hot');
const items = ref<MediaItem[]>([]);
const nextCursor = ref<string | null>(null);
const hasMore = ref(true);
const loadError = ref(false);
const draftFormat = ref<MediaFormatValue | ''>('');
const draftLanguage = ref<NonNullable<MediaWorksQuery['language']> | ''>('');
const filters = ref<Pick<MediaWorksQuery, 'format' | 'language'>>({});
const panel = useTemplateRef<HTMLElement>('panel');
const scrollContainer = ref<HTMLElement | Window | null>(null);
const loading = ref(false);
const me = ref<MediaMe | null>(null);
const preview = ref<PreviewTarget | null>(null);
let meRequestId = 0;
let controller: AbortController | undefined;
const seenIds = new Set<number>();

useInfiniteScroll(scrollContainer, load, {
    distance: 160,
    canLoadMore: () => hasMore.value && !loading.value && !loadError.value,
});

onMounted(() => {
    scrollContainer.value = panel.value?.closest<HTMLElement>('main.common-layout') ?? window;
});

// /me 成功表示当前是登录态；UserMedia.banned 只禁止投稿，不应禁用投喂。
const feedDisabled = computed(() => me.value === null);

function openPreview(item: MediaItem): void {
    const embedUrl = mediaEmbedUrl(item.format, item.suffix);
    const url = mediaExternalUrl(item.format, item.suffix);
    if (embedUrl === undefined || url === undefined) return;
    preview.value = { title: item.title, url, embedUrl };
}

function selectSort(value: MediaWorksSort): void {
    if (sort.value === value) return;
    sort.value = value;
}

function applyFilters(): void {
    filters.value = {
        format: draftFormat.value || undefined,
        language: draftLanguage.value || undefined,
    };
}

function clearFilters(): void {
    draftFormat.value = '';
    draftLanguage.value = '';
    filters.value = {};
}

function refresh(): void {
    controller?.abort();
    loading.value = false;
    items.value = [];
    seenIds.clear();
    nextCursor.value = null;
    hasMore.value = true;
    loadError.value = false;
    scrollContainer.value?.scrollTo({ top: 0 });
    void load();
}

function formatDate(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString(locale.value);
}

function formatHeat(value: number): string {
    return value.toFixed(2);
}

async function loadMe(): Promise<void> {
    const request = ++meRequestId;
    try {
        const value = await fetchMediaMe();
        if (request !== meRequestId) return;
        me.value = value;
        emit('me', me.value);
    } catch {
        if (request !== meRequestId) return;
        me.value = null;
        emit('me', null);
    }
}

async function load(): Promise<void> {
    if (loading.value || !hasMore.value) return;
    const request = new AbortController();
    const cursor = nextCursor.value;
    controller = request;
    loading.value = true;
    loadError.value = false;
    emit('loading', true);
    try {
        const result = await fetchMediaWorks({ sort: sort.value, limit: 20, ...filters.value, cursor: cursor ?? undefined }, request.signal);
        if (request.signal.aborted) return;
        if (result.has_more && (result.next_cursor === null || result.next_cursor === '' || result.next_cursor === cursor || result.items.length === 0)) throw new Error('media_cursor_not_advancing');
        for (const item of result.items) {
            if (seenIds.has(item.id)) continue;
            seenIds.add(item.id);
            items.value.push(item);
        }
        nextCursor.value = result.next_cursor;
        hasMore.value = result.has_more;
    } catch {
        if (request.signal.aborted) return;
        loadError.value = true;
    } finally {
        if (!request.signal.aborted) {
            loading.value = false;
            emit('loading', false);
        }
    }
}

function onFeed(result: MediaLikeResult, item: MediaItem): void {
    item.likes = result.likes;
    item.hot_now = result.hot_now;
    if (me.value) {
        me.value.balance = result.balance;
        me.value.daily_likes_used = result.daily_likes_used;
        emit('me', me.value);
    }
}

// 页面内登录 / 切账号会改变 sessionRevision，重新拉取 /me；meRequestId 防止旧会话响应覆盖。
watch(() => store.sessionRevision, () => {
    void loadMe();
}, { immediate: true });
watch([sort, filters], refresh, { immediate: true });
onScopeDispose(() => {
    controller?.abort();
    meRequestId++;
});

defineExpose({ refresh });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '加载中',
        type: '类型',
        allTypes: '全部类型',
        bilibiliVideo: 'B 站视频',
        bilibiliArticle: 'B 站专栏',
        saoleiPost: '扫雷网帖子',
        githubRepository: 'GitHub 仓库',
        allLanguages: '全部语言',
        otherLanguage: '其他',
        apply: '筛选',
        clear: '清空',
        loadFailed: '加载失败，已加载内容保留。',
        retry: '重试',
        loadMore: '加载更多',
        end: '已加载完毕',
    } },
    en: { local: {
        loading: 'Loading',
        type: 'Type',
        allTypes: 'All types',
        bilibiliVideo: 'Bilibili video',
        bilibiliArticle: 'Bilibili article',
        saoleiPost: 'Saolei post',
        githubRepository: 'GitHub repository',
        allLanguages: 'All languages',
        otherLanguage: 'Other',
        apply: 'Filter',
        clear: 'Clear',
        loadFailed: 'Could not load works. Loaded items are kept.',
        retry: 'Retry',
        loadMore: 'Load more',
        end: 'All works loaded',
    } },
    es: { local: {
        loading: 'Cargando',
        type: 'Tipo',
        allTypes: 'Todos los tipos',
        bilibiliVideo: 'Vídeo de Bilibili',
        bilibiliArticle: 'Artículo de Bilibili',
        saoleiPost: 'Publicación de Saolei',
        githubRepository: 'Repositorio de GitHub',
        allLanguages: 'Todos los idiomas',
        otherLanguage: 'Otros',
        apply: 'Filtrar',
        clear: 'Limpiar',
        loadFailed: 'No se pudieron cargar las obras. Se conservan las ya cargadas.',
        retry: 'Reintentar',
        loadMore: 'Cargar más',
        end: 'Todas las obras cargadas',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.media-filters,
.media-filters label,
.media-load-more {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
}

.media-filters {
    margin-bottom: 4px;
    gap: 4px 8px;
}

.media-filters :is(select, input[type="text"]) {
    min-width: 0;
    padding: 3px 4px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.media-load-more {
    justify-content: center;
    padding: 4px;
}

.media-filters :deep(.el-select) {
    width: 230px;
}
</style>
