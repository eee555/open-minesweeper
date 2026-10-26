<template>
    <section class="user-directory">
        <form class="user-directory-filters" @submit.prevent="applyFilters">
            <label class="user-directory-filter">
                <span>{{ t('accountlink.platform') }}</span>
                <select id="user-query-platform" v-model="draft.platform">
                    <option value="">{{ t('local.site') }}</option>
                    <option v-for="column in accountColumns" :key="column.platform" :value="column.platform">{{ t(`platform.${column.platform}`) }}</option>
                </select>
            </label>
            <label class="user-directory-filter">
                <span>ID</span>
                <input id="user-query-id" v-model="draft.id" type="text" :inputmode="draft.platform === 'm' ? 'text' : 'numeric'" :pattern="draft.platform === 'm' ? undefined : '[0-9]*'" :maxlength="draft.platform === '' ? 19 : draft.platform === 'm' ? 64 : 128" autocomplete="off">
            </label>
            <BaseButton native-type="submit" :loading="loading" data-cy="user-query-submit">
                {{ t('local.search') }}
            </BaseButton>
            <BaseButton data-cy="user-query-reset" @click="resetFilters">
                {{ t('local.reset') }}
            </BaseButton>
        </form>
        <p v-if="failed" class="text-danger" role="alert">
            {{ t('local.loadFailed') }}
            <BaseButton size="small" @click="load">
                {{ t('button.retry') }}
            </BaseButton>
        </p>
        <BaseTable v-loading="loading" class="user-directory-table" :table-style="{ width: 'auto', marginInline: 'auto' }" :empty="users.length === 0" :column-count="12" :empty-text="t('local.empty')" :aria-busy="loading">
            <template #head>
                <tr>
                    <th scope="col" rowspan="2" class="table-col-number" :aria-sort="ariaSort('id')">
                        <BaseTextButton :type="sort === 'id' ? 'primary' : 'default'" :aria-pressed="sort === 'id'" data-sort="id" @click="selectSort('id')">
                            {{ t('prop.userId') }} <span v-if="sort === 'id'" aria-hidden="true">{{ reverse ? '↓' : '↑' }}</span>
                        </BaseTextButton>
                    </th>
                    <th scope="col" rowspan="2">
                        {{ t('local.dateJoined') }}
                    </th>
                    <th scope="colgroup" colspan="4">
                        {{ t('local.accounts') }}
                    </th>
                    <th scope="colgroup" colspan="3">
                        {{ t('local.videoCount') }}
                    </th>
                    <th scope="colgroup" colspan="3">
                        {{ t('local.videoSize') }}
                    </th>
                </tr>
                <tr>
                    <th v-for="column in accountColumns" :key="column.platform" scope="col" class="user-directory-account" :class="{ 'user-directory-account-mineracer': column.platform === AccountLinkPlatform.Mineracer }" :style="{ '--account-id-width': column.width }">
                        <span class="user-directory-account-heading">{{ t(`platform.${column.platform}`) }} ID</span>
                    </th>
                    <th v-for="column in statisticsColumns" :key="column.field" scope="col" class="table-col-number" :aria-sort="ariaSort(column.field)">
                        <BaseTextButton :type="sort === column.field ? 'primary' : 'default'" :aria-pressed="sort === column.field" :data-sort="column.field" @click="selectSort(column.field)">
                            {{ t(column.label) }} <span v-if="sort === column.field" aria-hidden="true">{{ reverse ? '↓' : '↑' }}</span>
                        </BaseTextButton>
                    </th>
                </tr>
            </template>
            <tr v-for="user in users" :key="user.id">
                <td class="table-col-number">
                    <RouterLink :to="{ name: 'player_id', params: { id: user.id } }">
                        {{ user.id }}
                    </RouterLink>
                </td>
                <td><time :datetime="user.date_joined">{{ toISODateTimeString(new Date(user.date_joined)) }}</time></td>
                <td v-for="column in accountColumns" :key="column.platform" :data-platform="column.platform" class="user-directory-account" :class="{ 'user-directory-account-mineracer': column.platform === AccountLinkPlatform.Mineracer }" :style="{ '--account-id-width': column.width }" :title="user.accounts[column.platform]">
                    <span class="user-directory-account-id">
                        <a v-if="user.accounts[column.platform] && column.platform !== AccountLinkPlatform.Mineracer" :href="platformlist[column.platform].profile(user.accounts[column.platform] ?? '')" target="_blank" rel="noopener noreferrer">{{ user.accounts[column.platform] }}</a>
                        <template v-else>
                            {{ user.accounts[column.platform] }}
                        </template>
                    </span>
                </td>
                <td v-for="column in statisticsColumns" :key="column.field" class="table-col-number" :data-field="column.field" :title="column.bytes ? `${numberFormatter.format(user.statistics[column.field])} B` : undefined">
                    {{ column.bytes ? displaySize(user.statistics[column.field]) : numberFormatter.format(user.statistics[column.field]) }}
                </td>
            </tr>
        </BaseTable>
        <div class="user-directory-pagination">
            <ElPagination v-model:current-page="page" v-model:page-size="pageSize" layout="total, sizes, prev, pager, next, jumper" :page-sizes="[20, 50, 100]" :total="total" />
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/text.css';

import { ElPagination, vLoading } from 'element-plus';
import { computed, onScopeDispose, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { fetchUserDirectory } from '@/services/userDirectoryService';
import type { DirectoryUser, UserDirectoryFilters, UserDirectorySort } from '@/services/userDirectoryService';
import { AccountLinkPlatform, platformlist } from '@/utils/accountlinks/platforms';
import { toISODateTimeString } from '@/utils/datetime';
import { formatBytes } from '@/utils/strings';

const accountColumns = [
    { platform: AccountLinkPlatform.Saolei, width: '5ch' }, { platform: AccountLinkPlatform.MSGames, width: '5ch' },
    { platform: AccountLinkPlatform.WoM, width: '8ch' }, { platform: AccountLinkPlatform.Mineracer, width: '20ch' },
] as const;
const statisticsColumns = [
    { field: 'video_num_total', label: 'local.ordinary', bytes: false }, { field: 'video_num_tournament', label: 'tournament.tournament', bytes: false }, { field: 'video_num_all', label: 'all', bytes: false },
    { field: 'video_size_total', label: 'local.ordinary', bytes: true }, { field: 'video_size_tournament', label: 'tournament.tournament', bytes: true }, { field: 'video_size_all', label: 'all', bytes: true },
] as const;
const emptyFilters: UserDirectoryFilters = { platform: '', id: '' };
const draft = reactive({ ...emptyFilters });
const filters = ref({ ...emptyFilters });
const sort = ref<UserDirectorySort>('id');
const reverse = ref(false);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const users = ref<DirectoryUser[]>([]);
const loading = ref(false);
const failed = ref(false);
let controller: AbortController | undefined;
let requestId = 0;

function applyFilters() {
    page.value = 1;
    filters.value = { platform: draft.platform, id: draft.id.trim() };
}

function resetFilters() {
    Object.assign(draft, emptyFilters);
    applyFilters();
}

function selectSort(field: UserDirectorySort) {
    reverse.value = sort.value === field ? !reverse.value : field !== 'id';
    sort.value = field;
    page.value = 1;
}

function ariaSort(field: UserDirectorySort): 'none' | 'ascending' | 'descending' {
    return sort.value !== field ? 'none' : reverse.value ? 'descending' : 'ascending';
}

function displaySize(value: number) {
    return value < 0 ? `-${formatBytes(-value)}` : formatBytes(value);
}

async function load() {
    controller?.abort();
    controller = new AbortController();
    const { signal } = controller;
    const request = ++requestId;
    loading.value = true;
    failed.value = false;
    try {
        const result = await fetchUserDirectory({ ...filters.value, sort: sort.value, reverse: reverse.value, page: page.value, page_size: pageSize.value }, signal);
        if (request !== requestId) return;
        users.value = result.users;
        total.value = result.count;
        const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value));
        if (page.value > lastPage) page.value = lastPage;
    } catch (error) {
        if (signal.aborted || request !== requestId) return;
        failed.value = true;
        users.value = [];
        total.value = 0;
        httpErrorNotification(error);
    } finally {
        if (request === requestId) loading.value = false;
    }
}

watch(pageSize, () => {
    page.value = 1;
});
watch([filters, sort, reverse, page, pageSize], () => {
    void load();
}, { immediate: true });
onScopeDispose(() => {
    requestId++; controller?.abort();
});

const i18nMessages = {
    'zh-cn': { local: {
        site: '本站',
        dateJoined: '注册时间',
        accounts: '关联账号',
        videoCount: '录像数量',
        videoSize: '录像占用空间',
        ordinary: '非比赛',
        search: '查询',
        reset: '清空',
        empty: '没有符合条件的用户',
        loadFailed: '用户列表加载失败',
    } },
    en: { local: {
        site: 'This site',
        dateJoined: 'Date joined',
        accounts: 'Linked accounts',
        videoCount: 'Replay count',
        videoSize: 'Replay storage',
        ordinary: 'Non-tournament',
        search: 'Search',
        reset: 'Clear',
        empty: 'No matching users',
        loadFailed: 'Unable to load users',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });
const numberFormatter = computed(() => new Intl.NumberFormat(locale.value));
</script>

<style scoped>
.user-directory-filters {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: 8px;
}

.user-directory-filter {
    display: flex;
    flex: 0 1 12rem;
    flex-direction: column;
    gap: 2px;
}

.user-directory-filter input,
.user-directory-filter select {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    padding: 4px 6px;
    border: 1px solid var(--el-border-color);
    border-radius: 0;
    background: var(--el-fill-color-blank);
    color: var(--el-text-color-primary);
    font: inherit;
}

.user-directory-filter input:focus-visible,
.user-directory-filter select:focus-visible {
    outline: 2px solid var(--el-color-primary);
    outline-offset: 1px;
}

.user-directory-table :deep(td) {
    white-space: nowrap;
}

.user-directory-account {
    text-align: right;
}

.user-directory-account-mineracer {
    text-align: left;
}

.user-directory-account-heading,
.user-directory-account-id {
    display: block;
    width: var(--account-id-width);
}

.user-directory-account-heading {
    overflow-wrap: anywhere;
    white-space: normal;
}

.user-directory-account-id {
    overflow: hidden;
    text-overflow: ellipsis;
}

.user-directory-pagination {
    margin-top: 8px;
    overflow-x: auto;
}
</style>
