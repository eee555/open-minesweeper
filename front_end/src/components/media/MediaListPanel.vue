<template>
    <section class="media-panel">
        <div v-if="loading" class="media-toolbar">
            <span class="text-secondary text-small">{{ t('local.loading') }}</span>
        </div>
        <ul v-if="items.length > 0" class="media-list">
            <li v-for="item in items" :key="item.id">
                <MediaCard
                    :media="item" :show-status="showStatus" :show-reject-info="showRejectInfo"
                    :feed-disabled="feedDisabled" :feed-balance="me?.balance ?? null" @feed="onFeed"
                />
            </li>
        </ul>
        <p v-else class="media-empty">
            {{ t('media.empty') }}
        </p>
        <ElPagination
            v-model:current-page="page" v-model:page-size="pageSize"
            layout="total, prev, pager, next" :total="total"
        />
    </section>
</template>

<script setup lang="ts">
import { ElPagination } from 'element-plus';
import { computed, onActivated, onScopeDispose, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import MediaCard from './MediaCard.vue';

import { httpErrorNotification } from '@/components/Notifications';
import type { MediaItem, MediaLikeResult, MediaMe, MediaPage, MediaRankSort } from '@/services/mediaService';
import { fetchLatestMedia, fetchMediaMe, fetchMediaRanking, fetchPendingMedia, fetchRejectedMedia } from '@/services/mediaService';
import { store } from '@/store';

import '@/components/media/media.css';

const props = defineProps({
    source: { type: String as PropType<'ranking' | 'latest' | 'pending' | 'rejected'>, required: true },
    sort: { type: String as PropType<MediaRankSort>, default: undefined },
    showStatus: { type: Boolean, default: false },
    showRejectInfo: { type: Boolean, default: false },
});

const items = ref<MediaItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const me = ref<MediaMe | null>(null);
let requestId = 0;
let meRequestId = 0;

// /me 成功表示当前是登录态；UserMedia.banned 只禁止投稿，不应禁用投喂。
const feedDisabled = computed(() => me.value === null);

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
    const start = (page.value - 1) * pageSize.value;
    try {
        let result: MediaPage;
        if (props.source === 'ranking') result = await fetchMediaRanking(props.sort ?? 'hot', start, pageSize.value);
        else if (props.source === 'latest') result = await fetchLatestMedia(start, pageSize.value);
        else if (props.source === 'rejected') result = await fetchRejectedMedia(start, pageSize.value);
        else result = await fetchPendingMedia(start, pageSize.value);
        if (request !== requestId) return;
        items.value = result.items;
        total.value = result.total;
    } catch (error) {
        if (request !== requestId) return;
        items.value = [];
        total.value = 0;
        httpErrorNotification(error);
    } finally {
        if (request === requestId) loading.value = false;
    }
}

function onFeed(result: MediaLikeResult): void {
    if (me.value) me.value.balance = result.balance;
}

// keep-alive 缓存的 tab 切回时必须重新拉列表，否则审核通过的新作品只会出现在《最新》。
let activatedOnce = false;
onActivated(() => {
    if (!activatedOnce) {
        activatedOnce = true;
        return;
    }
    void load();
});

// 页面内登录 / 切账号会改变 sessionRevision，重新拉取 /me；meRequestId 防止旧会话响应覆盖。
watch(() => store.sessionRevision, () => {
    void loadMe();
}, { immediate: true });
watch([page, pageSize], () => {
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
