<template>
    <section class="media-user">
        <div class="media-toolbar">
            <BaseTextButton
                v-for="option in sortOptions" :key="option.value" underline="never"
                :aria-pressed="sort === option.value" @click="changeSort(option.value)"
            >
                {{ option.label }}
            </BaseTextButton>
            <BaseTextButton underline="never" @click="toggleOrder">
                {{ order === 'desc' ? t('local.desc') : t('local.asc') }}
            </BaseTextButton>
        </div>
        <BaseTable :empty="items.length === 0" :empty-text="t('media.empty')" :column-count="7">
            <template #head>
                <tr>
                    <th scope="col">
                        {{ t('media.title') }}
                    </th>
                    <th scope="col">
                        {{ t('media.status') }}
                    </th>
                    <th scope="col">
                        {{ t('media.language') }}
                    </th>
                    <th scope="col">
                        {{ t('media.publishedAt') }}
                    </th>
                    <th scope="col">
                        {{ t('media.likesCount') }}
                    </th>
                    <th scope="col">
                        {{ t('media.rejectReason') }}
                    </th>
                    <th scope="col">
                        {{ t('media.rejectedBy') }}
                    </th>
                </tr>
            </template>
            <tr v-for="item in items" :key="item.id">
                <td><a class="link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title || t('media.titleMissing') }}</a></td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ item.language || t('media.unknownLanguage') }}</td>
                <td>{{ item.created_at }}</td>
                <td>{{ item.likes }}</td>
                <td>{{ item.reject_reason }}</td>
                <td><PlayerName v-if="item.rejected_by" :user-id="item.rejected_by" /></td>
            </tr>
        </BaseTable>
        <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, prev, pager, next" :total="total" />
    </section>
</template>

<script setup lang="ts">
import { ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaItem, MediaSortKey, MediaStatusValue } from '@/services/mediaService';
import { fetchUserMedia } from '@/services/mediaService';

import '@/components/media/media.css';

const route = useRoute();
const userId = computed(() => Number(Array.isArray(route.params.id) ? route.params.id[0] : route.params.id));

const sort = ref<MediaSortKey>('hot');
const order = ref<'asc' | 'desc'>('desc');
const page = ref(1);
const pageSize = ref(20);
const items = ref<MediaItem[]>([]);
const total = ref(0);
let requestId = 0;

const sortOptions = computed(() => [
    { value: 'hot' as const, label: t('media.sortHot') },
    { value: 'likes' as const, label: t('media.sortLikes') },
    { value: 'created_at' as const, label: t('media.sortCreatedAt') },
]);

function statusLabel(status: MediaStatusValue): string {
    return t({ pending: 'media.pendingStatus', verified: 'media.verifiedStatus', rejected: 'media.rejectedStatus' }[status]);
}

function changeSort(value: MediaSortKey): void {
    sort.value = value;
    page.value = 1;
}

function toggleOrder(): void {
    order.value = order.value === 'desc' ? 'asc' : 'desc';
    page.value = 1;
}

async function load(): Promise<void> {
    const request = ++requestId;
    try {
        const result = await fetchUserMedia(userId.value, sort.value, order.value, page.value, pageSize.value);
        if (request !== requestId) return;
        items.value = result.items;
        total.value = result.total;
    } catch (error) {
        if (request !== requestId) return;
        items.value = [];
        total.value = 0;
        httpErrorNotification(error);
    }
}

watch([userId, sort, order, page, pageSize], () => {
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
});

const i18nMessages = {
    'zh-cn': { local: { desc: '降序', asc: '升序' } },
    en: { local: { desc: 'Descending', asc: 'Ascending' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
