<template>
    <section class="media-panel">
        <BaseTable
            table-class="media-works-table" :empty="items.length === 0" :column-count="5"
            :empty-text="loading ? t('local.loading') : t('media.empty')"
        >
            <template #head>
                <tr>
                    <th scope="col">
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
                <td>
                    <button
                        v-if="item.embed_url" type="button" class="link media-preview-link"
                        data-cy="media-preview-link" :title="t('media.preview')" @click="openPreview(item)"
                    >
                        {{ item.title || t('media.titleMissing') }}
                    </button>
                    <a v-else class="link" data-cy="media-title-link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title || t('media.titleMissing') }}</a>
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
        <ElPagination
            v-model:current-page="page" v-model:page-size="pageSize"
            layout="total, prev, pager, next" :total="total"
        />
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
import { ElDialog, ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import MediaFeedButton from './MediaFeedButton.vue';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaItem, MediaLikeResult, MediaMe, MediaPage } from '@/services/mediaService';
import { fetchLatestMedia, fetchMediaMe, fetchMediaRanking } from '@/services/mediaService';
import { store } from '@/store';

import '@/components/media/media.css';

type WorksSort = 'latest' | 'hot' | 'likes';
interface PreviewTarget { title: string; url: string; embedUrl: string }

const emit = defineEmits<{ loading: [value: boolean] }>();

const sort = ref<WorksSort>('hot');
const items = ref<MediaItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const me = ref<MediaMe | null>(null);
const preview = ref<PreviewTarget | null>(null);
let requestId = 0;
let meRequestId = 0;

// /me 成功表示当前是登录态；UserMedia.banned 只禁止投稿，不应禁用投喂。
const feedDisabled = computed(() => me.value === null);

function openPreview(item: MediaItem): void {
    if (item.embed_url === null || item.embed_url === '') return;
    preview.value = { title: item.title, url: item.url, embedUrl: item.embed_url };
}

function selectSort(value: WorksSort): void {
    if (sort.value === value) return;
    sort.value = value;
    page.value = 1;
}

function formatDate(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
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
    } catch {
        if (request !== meRequestId) return;
        me.value = null;
    }
}

async function load(): Promise<void> {
    const request = ++requestId;
    loading.value = true;
    emit('loading', true);
    const start = (page.value - 1) * pageSize.value;
    const rankSort = sort.value === 'hot' ? 'hot' : 'likes';
    try {
        const result: MediaPage = sort.value === 'latest'
            ? await fetchLatestMedia(start, pageSize.value)
            : await fetchMediaRanking(rankSort, start, pageSize.value);
        if (request !== requestId) return;
        items.value = result.items;
        total.value = result.total;
    } catch (error) {
        if (request !== requestId) return;
        items.value = [];
        total.value = 0;
        httpErrorNotification(error);
    } finally {
        if (request === requestId) {
            loading.value = false;
            emit('loading', false);
        }
    }
}

function onFeed(result: MediaLikeResult, item: MediaItem): void {
    item.likes = result.likes;
    item.hot_now = result.hot_now;
    if (me.value) me.value.balance = result.balance;
}

// 页面内登录 / 切账号会改变 sessionRevision，重新拉取 /me；meRequestId 防止旧会话响应覆盖。
watch(() => store.sessionRevision, () => {
    void loadMe();
}, { immediate: true });
watch([sort, page, pageSize], () => {
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
    meRequestId++;
});

defineExpose({ refresh: load });

const i18nMessages = {
    'zh-cn': { local: {
        loading: '加载中',
    } },
    en: { local: {
        loading: 'Loading',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
