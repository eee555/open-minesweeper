<template>
    <section class="media-review">
        <div class="media-toolbar">
            <BaseButton :aria-pressed="view === 'pending'" @click="view = 'pending'">
                {{ t('local.pending') }}
            </BaseButton>
            <BaseButton :aria-pressed="view === 'rejected'" @click="view = 'rejected'">
                {{ t('local.rejected') }}
            </BaseButton>
            <BaseButton :aria-pressed="view === 'verified'" @click="view = 'verified'">
                {{ t('local.verified') }}
            </BaseButton>
            <BaseButton @click="load">
                {{ t('local.refresh') }}
            </BaseButton>
            <span v-if="!isStaff" class="text-danger text-small">{{ t('local.forbidden') }}</span>
        </div>
        <BaseTable v-if="isStaff" :empty="items.length === 0" :empty-text="t('media.empty')" :column-count="6">
            <template #head>
                <tr>
                    <th scope="col">
                        ID
                    </th>
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
                        {{ t('media.likesCount') }}
                    </th>
                    <th scope="col">
                        {{ t('local.actions') }}
                    </th>
                </tr>
            </template>
            <tr v-for="item in items" :key="item.id">
                <td>{{ item.id }}</td>
                <td>
                    <a class="link" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title || t('media.titleMissing') }}</a>
                    <span v-if="item.metadata_pending" class="text-small text-warning"> ({{ t('local.degraded') }})</span>
                </td>
                <td><PlayerName :user-id="item.user_id" /></td>
                <td>{{ item.status }}</td>
                <td>{{ item.likes }}</td>
                <td>
                    <button type="button" class="media-text-button" @click="select(item)">
                        {{ t('local.select') }}
                    </button>
                </td>
            </tr>
        </BaseTable>
        <div v-if="selected && isStaff" class="card media-review-form">
            <h2 class="card-title">
                {{ t('local.actions') }} #{{ selected.id }}
            </h2>
            <div class="media-review-fields">
                <label v-if="selected.metadata_pending">{{ t('local.titleField') }}<input v-model="form.title" class="media-input" data-cy="review-title" type="text" maxlength="200"></label>
                <label v-if="selected.metadata_pending" data-cy="review-external-author-id-field">
                    {{ t('local.externalAuthorId') }}<input v-model="form.externalAuthorId" class="media-input" data-cy="review-external-author-id" type="text" maxlength="128">
                </label>
                <label>{{ t('media.rejectReason') }}<input v-model="form.reason" class="media-input" type="text"></label>
            </div>
            <p v-if="selected.metadata_pending" class="text-secondary text-small" data-cy="review-id-hint">
                {{ t('local.idHint') }}
            </p>
            <p v-else class="text-secondary text-small" data-cy="review-identity-confirmed">
                {{ t('local.identityConfirmed') }}
            </p>
            <div class="media-toolbar">
                <BaseButton type="primary" :disabled="busy" @click="verify">
                    {{ t('local.verify') }}
                </BaseButton>
                <BaseButton :disabled="busy" @click="reject">
                    {{ t('local.reject') }}
                </BaseButton>
                <BaseButton :disabled="busy" @click="reopen">
                    {{ t('local.reopen') }}
                </BaseButton>
                <BaseButton :disabled="busy" @click="ban(true)">
                    {{ t('local.ban') }}
                </BaseButton>
                <BaseButton :disabled="busy" @click="ban(false)">
                    {{ t('local.unban') }}
                </BaseButton>
                <BaseButton v-if="isSuperuser" type="danger" :disabled="busy" @click="hardDelete">
                    {{ confirmDelete ? t('local.confirmDelete') : t('local.delete') }}
                </BaseButton>
            </div>
        </div>
        <ElPagination v-if="isStaff" v-model:current-page="page" :page-size="PAGE_SIZE" layout="total, prev, pager, next" :total="total" />
    </section>
</template>

<script setup lang="ts">
import { ElNotification, ElPagination } from 'element-plus';
import { computed, onScopeDispose, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import type { MediaItem, MediaPage, MediaVerifyPayload } from '@/services/mediaService';
import {
    deleteMediaAdmin, fetchLatestMedia, fetchPendingMedia, fetchRejectedMedia, rejectMediaAdmin,
    reopenMediaAdmin, setMediaBanned, verifyMediaAdmin,
} from '@/services/mediaService';
import { store } from '@/store';

import '@/components/media/media.css';

const PAGE_SIZE = 20;
type ReviewView = 'pending' | 'rejected' | 'verified';
const view = ref<ReviewView>('pending');
const items = ref<MediaItem[]>([]);
const total = ref(0);
const page = ref(1);
const selected = ref<MediaItem | null>(null);
const busy = ref(false);
const confirmDelete = ref(false);
const form = ref({ title: '', externalAuthorId: '', reason: '' });
const isStaff = computed(() => store.user.is_staff);
const isSuperuser = computed(() => store.user.is_superuser);
let requestId = 0;

async function load(): Promise<void> {
    if (!isStaff.value) return;
    const request = ++requestId;
    try {
        const start = (page.value - 1) * PAGE_SIZE;
        let result: MediaPage;
        if (view.value === 'pending') result = await fetchPendingMedia(start, PAGE_SIZE);
        else if (view.value === 'rejected') result = await fetchRejectedMedia(start, PAGE_SIZE);
        else result = await fetchLatestMedia(start, PAGE_SIZE);
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

function select(item: MediaItem): void {
    selected.value = item;
    confirmDelete.value = false;
    form.value = { title: item.title, externalAuthorId: '', reason: '' };
}

async function run(action: () => Promise<unknown>, nextView?: ReviewView): Promise<void> {
    if (busy.value || !selected.value) return;
    busy.value = true;
    try {
        await action();
        actionSuccessNotification();
        confirmDelete.value = false;
        if (nextView) {
            // 审核通过后切到「已通过」并保留选中项，站长才能直接硬删除刚通过的作品。
            page.value = 1;
            view.value = nextView;
        } else {
            selected.value = null;
        }
        await load();
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        busy.value = false;
    }
}

function verify(): void {
    const media = selected.value;
    if (!media) return;
    const degraded = media.metadata_pending;
    if (degraded && (!form.value.title.trim() || !form.value.externalAuthorId.trim())) {
        ElNotification({ message: t('local.missingVerifyFields'), type: 'error' });
        return;
    }
    // 投稿时后端已用上游 author_id 核对过绑定关系，只有降级投稿才需要管理员补填 id 核验。
    const payload: MediaVerifyPayload = degraded
        ? { id: media.id, title: form.value.title, external_author_id: form.value.externalAuthorId }
        : { id: media.id };
    void run(async () => {
        selected.value = await verifyMediaAdmin(payload);
    }, 'verified');
}

function reject(): void {
    const media = selected.value;
    if (media) void run(() => rejectMediaAdmin(media.id, form.value.reason));
}

function reopen(): void {
    const media = selected.value;
    if (media) void run(() => reopenMediaAdmin(media.id));
}

function ban(banned: boolean): void {
    const media = selected.value;
    if (media) void run(() => setMediaBanned(media.user_id, banned));
}

function hardDelete(): void {
    if (!confirmDelete.value) {
        confirmDelete.value = true;
        return;
    }
    const media = selected.value;
    if (media) void run(() => deleteMediaAdmin(media.id));
}

watch([view, page, isStaff], () => {
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++;
});

const i18nMessages = {
    'zh-cn': { local: {
        pending: '待审核',
        rejected: '已驳回',
        verified: '已通过',
        refresh: '刷新',
        forbidden: '仅管理员可用',
        actions: '操作',
        select: '选择',
        titleField: '标题',
        externalAuthorId: '外站作者 id',
        verify: '通过',
        reject: '驳回',
        reopen: '改回待审核',
        ban: '封禁投稿',
        unban: '解封',
        delete: '硬删除',
        confirmDelete: '确认硬删除',
        degraded: '待补全',
        idHint: '外站作者 id 仅用于核验投稿人绑定关系，不会保存。',
        identityConfirmed: '投稿时已核验作者身份，无需填写外站作者 id。',
        missingVerifyFields: '待补全作品通过前必须填写标题与外站作者 id',
    } },
    en: { local: {
        pending: 'Pending',
        rejected: 'Rejected',
        verified: 'Verified',
        refresh: 'Refresh',
        forbidden: 'Moderators only',
        actions: 'Actions',
        select: 'Select',
        titleField: 'Title',
        externalAuthorId: 'External author id',
        verify: 'Verify',
        reject: 'Reject',
        reopen: 'Reopen',
        ban: 'Ban submissions',
        unban: 'Unban',
        delete: 'Hard delete',
        confirmDelete: 'Confirm hard delete',
        degraded: 'Metadata pending',
        idHint: 'The external author id is used only to verify the submitter link, never stored',
        identityConfirmed: 'The author was already verified on submission; no external author id is needed',
        missingVerifyFields: 'A degraded submission requires both a title and an external author id',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="css">
.media-review-form {
    margin-top: 8px;
}

.media-review-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
}

.media-review-fields > label {
    display: flex;
    flex: 1 1 240px;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
}

.media-input {
    flex: 1 1 160px;
    min-width: 0;
    padding: 4px 6px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.media-input:focus-visible {
    outline: 2px solid var(--ui-color-primary);
}
</style>
