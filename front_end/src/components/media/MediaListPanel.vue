<template>
    <section class="media-panel">
        <div class="media-toolbar">
            <BaseButton v-if="showSubmit" type="primary" @click="dialogOpen = true">
                {{ t('local.submit') }}
            </BaseButton>
            <span v-if="me" class="text-secondary text-small">{{ t('local.balance') }}: {{ me.balance }}</span>
            <span v-if="loading" class="text-secondary text-small">{{ t('local.loading') }}</span>
        </div>
        <ul v-if="items.length > 0" class="media-list">
            <li v-for="item in items" :key="item.id">
                <MediaCard
                    :media="item" :show-status="showStatus" :show-reject-info="showRejectInfo"
                    :feed-disabled="feedDisabled" @feed="onFeed"
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
        <SubmitMediaDialog v-if="dialogOpen" @close="dialogOpen = false" @submitted="onSubmitted" />
    </section>
</template>

<script setup lang="ts">
import { ElNotification, ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import MediaCard from './MediaCard.vue';
import SubmitMediaDialog from './SubmitMediaDialog.vue';

import BaseButton from '@/components/common/BaseButton.vue';
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
    showSubmit: { type: Boolean, default: false },
});

const router = useRouter();

const items = ref<MediaItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const me = ref<MediaMe | null>(null);
const dialogOpen = ref(false);
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

function onSubmitted(media: MediaItem): void {
    dialogOpen.value = false;
    ElNotification({
        title: t('local.submitDone'),
        message: media.metadata_pending ? t('local.degradedHint') : t('local.normalHint'),
        type: 'success',
    });
    if (media.metadata_pending) void router.replace({ name: 'works-pending' });
    void load();
}

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
        submit: '投稿作品',
        balance: '红宝石余额',
        loading: '加载中',
        submitDone: '投稿成功',
        normalHint: '作品已进入审核队列',
        degradedHint: '投稿已保留，标题由管理员审核时补全并核验外站账号',
    } },
    en: { local: {
        submit: 'Submit a work',
        balance: 'Rubies',
        loading: 'Loading',
        submitDone: 'Submitted',
        normalHint: 'Your work is now in the review queue',
        degradedHint: 'Submission kept; a moderator will fill in the title and verify the external account',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
