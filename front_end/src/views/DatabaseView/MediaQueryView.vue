<template>
    <section class="media-query">
        <div class="media-toolbar">
            <select v-model="field" class="base-select" :aria-label="t('local.field')">
                <option value="title">
                    {{ t('local.fieldTitle') }}
                </option>
                <option value="suffix">
                    {{ t('local.fieldSuffix') }}
                </option>
            </select>
            <select v-model="mode" class="base-select" :aria-label="t('local.mode')">
                <option v-for="option in modes" :key="option" :value="option">
                    {{ option }}
                </option>
            </select>
            <input v-model="value" class="media-input" type="text" maxlength="200" :aria-label="t('local.value')" @keydown.enter="search">
            <BaseButton type="primary" :loading="loading" @click="search">
                {{ t('local.search') }}
            </BaseButton>
        </div>
        <p v-if="error" class="text-danger">
            {{ error }}
        </p>
        <BaseTable :empty="pagedItems.length === 0" :empty-text="t('media.empty')" :column-count="8">
            <template #head>
                <tr>
                    <th scope="col">
                        {{ t('media.title') }}
                    </th>
                    <th scope="col">
                        {{ t('media.author') }}
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
            <tr v-for="item in pagedItems" :key="item.id">
                <td><a class="link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title || t('media.titleMissing') }}</a></td>
                <td><PlayerName :user-id="item.user_id" /></td>
                <td>{{ statusLabel(item.status) }}</td>
                <td>{{ item.language || t('media.unknownLanguage') }}</td>
                <td>{{ item.created_at }}</td>
                <td>{{ item.likes }}</td>
                <td>{{ item.reject_reason }}</td>
                <td><PlayerName v-if="item.rejected_by" :user-id="item.rejected_by" /></td>
            </tr>
        </BaseTable>
        <ElPagination v-model:current-page="page" :page-size="PAGE_SIZE" layout="total, prev, pager, next" :total="items.length" />
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { ElPagination } from 'element-plus';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaItem, MediaQueryErrorBody, MediaQueryField, MediaQueryMode, MediaStatusValue } from '@/services/mediaService';
import { queryMedia } from '@/services/mediaService';

import '@/components/media/media.css';

const PAGE_SIZE = 20;
const modes: MediaQueryMode[] = ['exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex'];

const field = ref<MediaQueryField>('title');
const mode = ref<MediaQueryMode>('icontains');
const value = ref('');
const items = ref<MediaItem[]>([]);
const page = ref(1);
const loading = ref(false);
const error = ref('');

const pagedItems = computed(() => items.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));

function statusLabel(status: MediaStatusValue): string {
    return t({ pending: 'media.pendingStatus', verified: 'media.verifiedStatus', rejected: 'media.rejectedStatus' }[status]);
}

async function search(): Promise<void> {
    if (!value.value.trim()) return;
    loading.value = true;
    error.value = '';
    try {
        const result = await queryMedia(mode.value, value.value, field.value, 1000);
        items.value = result.items;
        page.value = 1;
    } catch (caught) {
        items.value = [];
        if (isAxiosError<MediaQueryErrorBody>(caught) && caught.response?.status === 400) {
            error.value = caught.response.data?.detail ?? caught.response.data?.code ?? t('local.searchFailed');
        } else {
            httpErrorNotification(caught);
        }
    } finally {
        loading.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        field: '字段',
        fieldTitle: '标题',
        fieldSuffix: '外链标识',
        mode: '匹配模式',
        value: '查询内容',
        search: '查询',
        searchFailed: '查询失败',
    } },
    en: { local: {
        field: 'Field',
        fieldTitle: 'Title',
        fieldSuffix: 'External ID',
        mode: 'Match mode',
        value: 'Query',
        search: 'Search',
        searchFailed: 'Search failed',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
