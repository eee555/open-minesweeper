<template>
    <div class="identifier-query">
        <form class="query-form" @submit.prevent="queryPlayer">
            <label for="identifier-player-id">{{ t('local.playerId') }}</label>
            <ElInput id="identifier-player-id" v-model="playerId" inputmode="numeric" :disabled="loading" />
            <BaseButton native-type="submit" :loading="loading" :disabled="!validPlayerId">
                {{ t('local.byPlayer') }}
            </BaseButton>
        </form>
        <form class="query-form" @submit.prevent="queryIdentifier">
            <label for="identifier-mode">{{ t('local.mode') }}</label>
            <select id="identifier-mode" v-model="matchMode" :disabled="loading" aria-describedby="identifier-mode-help">
                <option v-for="mode in matchModes" :key="mode" :value="mode">
                    {{ t(`local.modes.${mode}`) }}
                </option>
            </select>
            <label v-if="matchMode !== 'regex'" class="checkbox checkbox--small">
                <input id="identifier-ignore-case" v-model="ignoreCase" class="checkbox-input" type="checkbox" :disabled="loading">
                <span>{{ t('local.ignoreCase') }}</span>
            </label>
            <label for="identifier-text">{{ t('local.identifier') }}</label>
            <ElInput id="identifier-text" v-model="identifier" maxlength="128" :disabled="loading" />
            <BaseButton native-type="submit" :loading="loading" :disabled="identifier.length === 0">
                {{ t('local.byIdentifier') }}
            </BaseButton>
            <BaseOverlay underline="always">
                {{ t('local.rateLimits') }}
                <template #header>
                    {{ t('local.rateLimits') }}
                </template>
                <template #overlay>
                    <div class="rate-limit-details">
                        <BaseTable>
                            <template #head>
                                <tr>
                                    <th scope="col">
                                        {{ t('local.limitGroup') }}
                                    </th>
                                    <th scope="col">
                                        {{ t('local.matchingOptions') }}
                                    </th>
                                    <th scope="col">
                                        {{ t('local.quota') }}
                                    </th>
                                </tr>
                            </template>
                            <tr v-for="group in limitGroups" :key="group">
                                <th scope="row">
                                    {{ t(`local.groups.${group}.name`) }}
                                </th>
                                <td>{{ t(`local.groups.${group}.matches`) }}</td>
                                <td>{{ t(group === 'exact' ? 'ratelimit.requestsPerSecond' : 'ratelimit.requestsPerMinute', { count: limitCounts[group] }) }}</td>
                            </tr>
                        </BaseTable>
                        <p>{{ t('local.limitHint') }}</p>
                        <p>{{ t('local.matchLimit') }}</p>
                    </div>
                </template>
            </BaseOverlay>
        </form>
        <p id="identifier-mode-help" class="text-small">
            {{ t('local.matchHint') }}
        </p>
        <IdentifierDisplayOptions />
        <p v-if="queryTooBroad" role="alert" class="text-danger">
            {{ t('local.tooManyMatches') }}
        </p>
        <template v-if="queried">
            <BaseTable
                :empty="pageRows.length === 0" :empty-text="t('local.empty')" :column-count="isStaff ? 4 : 2"
                aria-live="polite" data-cy="identifier-table"
            >
                <template #head>
                    <tr>
                        <th scope="col" :aria-sort="sortState(sortOrder, sortField === 'identifier')">
                            <BaseButton size="small" text :aria-label="t('local.identifier')" data-cy="sort-identifier" @click="toggleSort('identifier')">
                                {{ t('local.identifier') }}
                                <SortIcon :state="sortState(sortOrder, sortField === 'identifier')" />
                            </BaseButton>
                        </th>
                        <th scope="col">
                            <div class="identifier-header">
                                <span>{{ t('local.owner') }}</span>
                                <Tippy ref="ownerFilterTippy" interactive trigger="click" placement="bottom-start" :append-to="appendToBody">
                                    <BaseButton size="small" text :aria-label="t('local.filterOwner')" data-cy="filter-owner-trigger">
                                        <i class="pi" :class="ownerFilter === null ? 'pi-filter' : 'pi-filter-fill'" aria-hidden="true" />
                                    </BaseButton>
                                    <template #content="{ hide }">
                                        <div class="card card-small owner-filter" role="group" :aria-label="t('local.filterOwner')" data-cy="owner-filter-panel" @click.stop @keydown.esc="hide()">
                                            <input v-model="ownerSearch" class="base-select owner-filter__search" type="text" :placeholder="t('local.filterOwner')" :aria-label="t('local.filterOwner')" data-cy="filter-owner-search">
                                            <BaseListbox :model-value="ownerFilter ?? []" :options="ownerListboxOptions" multiple :aria-label="t('local.filterOwner')" data-cy="filter-owner" @update:model-value="setOwnerFilter">
                                                <template #option="{ option }">
                                                    <PlayerName v-if="option.value > 0" :user-id="option.value" :interactive="false" />
                                                    <span v-else>{{ t('local.unbound') }}</span>
                                                </template>
                                            </BaseListbox>
                                            <BaseButton size="small" text data-cy="filter-owner-clear" @click="clearOwnerFilter(); hide()">
                                                {{ t('local.clearFilter') }}
                                            </BaseButton>
                                        </div>
                                    </template>
                                </Tippy>
                            </div>
                        </th>
                        <th v-if="isStaff" scope="col" :aria-sort="sortState(sortOrder, sortField === 'safe')">
                            <BaseButton size="small" text aria-label="safe" data-cy="sort-safe" @click="toggleSort('safe')">
                                safe
                                <SortIcon :state="sortState(sortOrder, sortField === 'safe')" />
                            </BaseButton>
                        </th>
                        <th v-if="isStaff" scope="col">
                            {{ t('prop.action') }}
                        </th>
                    </tr>
                </template>
                <tr v-for="row in pageRows" :key="row.identifier">
                    <td class="identifier-value">
                        <IdentifierText :text="row.identifier" />
                        <IconCopy :text="row.identifier" />
                    </td>
                    <td>
                        <PlayerName v-if="row.user_id !== null" :user-id="row.user_id" />
                        <span v-else>{{ t('local.unbound') }}</span>
                    </td>
                    <td v-if="isStaff">
                        {{ row.safe }}
                    </td>
                    <td v-if="isStaff">
                        <Tippy interactive trigger="click" placement="bottom-end" :append-to="appendToBody">
                            <BaseButton size="small" text :disabled="loading || updating" :aria-label="t('prop.action')" data-cy="identifier-actions" :data-identifier="row.identifier">
                                <i class="pi pi-ellipsis-h" aria-hidden="true" />
                            </BaseButton>
                            <template #content="{ hide }">
                                <div class="card card-small identifier-actions">
                                    <BaseButton size="small" :disabled="updating || (row.safe === true && row.user_id !== null)" @click="hide(); toggleSafe(row)">
                                        {{ t('local.setSafe', { value: String(!row.safe) }) }}
                                    </BaseButton>
                                    <BaseButton size="small" :disabled="updating || (row.safe !== true && row.user_id === null)" @click="hide(); openBinding(row)">
                                        {{ t('local.bindUser') }}
                                    </BaseButton>
                                    <p v-if="row.user_id !== null" class="text-small">
                                        {{ t('local.unbindFirst') }}
                                    </p>
                                    <p v-else-if="row.safe === false" class="text-small">
                                        {{ t('local.approveFirst') }}
                                    </p>
                                </div>
                            </template>
                        </Tippy>
                    </td>
                </tr>
            </BaseTable>
            <BasePagination
                v-model:current-start="currentStart" v-model:page-size="pageSize"
                :total="total" :page-size-options="[10, 25, 50, 100]" data-cy="identifier-pagination"
            />
        </template>
        <ElDialog v-if="bindingTarget" v-model="bindingOpen" :title="t('local.bindUser')" width="min(28rem, 95vw)" :close-on-click-modal="!updating" :close-on-press-escape="!updating" :show-close="!updating" @closed="bindingTarget = null">
            <form class="binding-form" @submit.prevent="saveBinding">
                <IdentifierText :text="bindingTarget.identifier" />
                <label for="identifier-bind-user">{{ t('local.playerId') }}</label>
                <ElInput id="identifier-bind-user" v-model="bindingId" inputmode="numeric" :disabled="updating" />
                <p class="text-small">
                    {{ t('local.bindHint') }}
                </p>
                <BaseButton native-type="submit" :loading="updating" :disabled="!validBindingId">
                    {{ t('button.save') }}
                </BaseButton>
            </form>
        </ElDialog>
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import { isAxiosError } from 'axios';
import { ElDialog, ElInput } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import type { IdentifierResult, IdentifierSortField, IdentifierTableRow } from './identifierViewData';
import { filterIdentifiersByOwner, sliceIdentifiers, sortIdentifiers, toIdentifierTableRow } from './identifierViewData';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseListbox from '@/components/common/BaseListbox.vue';
import BaseOverlay from '@/components/common/BaseOverlay.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import { baseErrorNotification, httpErrorNotification } from '@/components/Notifications';
import PlayerName from '@/components/PlayerName.vue';
import IconCopy from '@/components/widgets/IconCopy.vue';
import IdentifierDisplayOptions from '@/components/widgets/IdentifierDisplayOptions.vue';
import IdentifierText from '@/components/widgets/IdentifierText.vue';
import $axios from '@/http';
import { fetchUserIdentifiers } from '@/services/userService';
import { store } from '@/store';

interface OwnerOption {
    id: number;
    label: string;
}

const matchModes = ['exact', 'contains', 'startswith', 'endswith', 'regex'] as const;
const limitGroups = ['exact', 'prefix', 'text', 'regex'] as const;
const limitCounts = { exact: 2, prefix: 10, text: 6, regex: 2 } as const;
type MatchMode = typeof matchModes[number];
const insensitiveModes = { exact: 'iexact', contains: 'icontains', startswith: 'istartswith', endswith: 'iendswith', regex: 'regex' } as const;
const playerId = ref('');
const identifier = ref('');
const matchMode = ref<MatchMode>('exact');
const ignoreCase = ref(false);
const apiMode = computed(() => (ignoreCase.value ? insensitiveModes[matchMode.value] : matchMode.value));
const loading = ref(false);
const updating = ref(false);
const isStaff = computed(() => store.user.is_staff);
const bindingTarget = ref<IdentifierResult | null>(null);
const bindingOpen = ref(false);
const bindingId = ref('');
const validBindingId = computed(() => (/^\d+$/).test(bindingId.value) && Number.isSafeInteger(Number(bindingId.value)));
const appendToBody = () => document.body;
const queried = ref(false);
const queryTooBroad = ref(false);
const results = ref<IdentifierResult[]>([]);
const currentStart = ref(1);
const pageSize = ref(25);
const sortField = ref<IdentifierSortField>('identifier');
const sortOrder = ref<number | undefined>(1);
const ownerFilter = ref<number[] | null>(null);
const tableData = computed<IdentifierTableRow[]>(() => results.value.map(toIdentifierTableRow));
const processed = computed(() => sortIdentifiers(filterIdentifiersByOwner(tableData.value, ownerFilter.value), sortField.value, sortOrder.value));
const total = computed(() => processed.value.length);
const first = computed(() => Math.max(0, Math.min(currentStart.value, total.value) - 1));
const pageRows = computed(() => sliceIdentifiers(processed.value, first.value, pageSize.value));
const ownerOptions = computed<OwnerOption[]>(() => [...new Set(tableData.value.map((row) => row.ownerKey))].sort((a, b) => a - b).map((id) => ({
    id,
    label: id === 0 ? t('local.unbound') : t('local.ownerId', { id }),
})));
const ownerSearch = ref('');
const visibleOwnerOptions = computed<OwnerOption[]>(() => {
    const keyword = ownerSearch.value.trim().toLowerCase();
    return keyword === '' ? ownerOptions.value : ownerOptions.value.filter((option) => option.label.toLowerCase().includes(keyword));
});
const ownerListboxOptions = computed(() => visibleOwnerOptions.value.map((option) => ({ value: option.id, label: option.label })));
const ownerFilterTippy = useTemplateRef<{ hide: () => void }>('ownerFilterTippy');

watch(ownerFilter, () => {
    currentStart.value = 1;
});

function toggleSort(field: IdentifierSortField) {
    const active = sortField.value === field;
    sortField.value = field;
    sortOrder.value = nextSortOrder(sortOrder.value, active, -1);
    currentStart.value = 1;
}

function setOwnerFilter(next: number[]) {
    ownerFilter.value = next.length > 0 ? next : null;
}

function clearOwnerFilter() {
    ownerFilter.value = null;
    ownerSearch.value = '';
}

function handleEscape(event: KeyboardEvent) {
    if (event.key === 'Escape') ownerFilterTippy.value?.hide();
}

onMounted(() => {
    document.addEventListener('keydown', handleEscape);
});
onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleEscape);
});

const validPlayerId = computed(() => (/^\d+$/).test(playerId.value) && Number.isSafeInteger(Number(playerId.value)) && Number(playerId.value) > 0);

async function query(getResults: () => Promise<IdentifierResult[]>) {
    if (loading.value || updating.value) return;
    loading.value = true;
    queryTooBroad.value = false;
    queried.value = false;
    results.value = [];
    currentStart.value = 1;
    ownerFilter.value = null;
    try {
        results.value = await getResults();
        queried.value = true;
    } catch (error) {
        if (isAxiosError<{ code?: string }>(error) && error.response?.status === 400 && error.response.data.code === 'too_many_matches') {
            queryTooBroad.value = true;
            queried.value = false;
            results.value = [];
        } else {
            httpErrorNotification(error);
        }
    } finally {
        loading.value = false;
    }
}

async function queryPlayer() {
    if (!validPlayerId.value || loading.value) return;
    const userId = Number(playerId.value);
    await query(async () => {
        if (isStaff.value) {
            const { data } = await $axios.get<{ items: IdentifierResult[] }>(`/api/identifier/query/user/${userId}`);
            return data.items;
        }
        return (await fetchUserIdentifiers(userId)).map((text) => ({ identifier: text, user_id: userId }));
    });
}

async function queryIdentifier() {
    if (identifier.value.length === 0 || loading.value) return;
    await query(async () => {
        const { data } = await $axios.get<{ items: IdentifierResult[] }>(`/api/identifier/query/${apiMode.value}`, { params: { identifier: identifier.value } });
        return data.items;
    });
}

async function updateIdentifier(row: IdentifierResult, path: 'bind' | 'safe', values: { id: number } | { safe: boolean }) {
    if (!isStaff.value || updating.value || loading.value) return false;
    updating.value = true;
    try {
        const { data } = await $axios.post<IdentifierResult>(`/api/identifier/${path}`, { identifier: row.identifier, ...values });
        results.value = results.value.map((result) => (result.identifier === row.identifier ? data : result));
        return true;
    } catch (error) {
        if (isAxiosError<{ detail?: unknown }>(error) && typeof error.response?.data.detail === 'string') {
            baseErrorNotification(t('msg.actionFail'), error.response.data.detail);
        } else {
            httpErrorNotification(error);
        }
        return false;
    } finally {
        updating.value = false;
    }
}

async function toggleSafe(row: IdentifierResult) {
    await updateIdentifier(row, 'safe', { safe: row.safe !== true });
}

function openBinding(row: IdentifierResult) {
    bindingTarget.value = row;
    bindingId.value = String(row.user_id ?? 0);
    bindingOpen.value = true;
}

async function saveBinding() {
    if (!bindingTarget.value || !validBindingId.value) return;
    if (await updateIdentifier(bindingTarget.value, 'bind', { id: Number(bindingId.value) })) bindingOpen.value = false;
}

watch(isStaff, () => {
    results.value = [];
    queried.value = false;
    bindingOpen.value = false;
    bindingTarget.value = null;
});

const i18nMessages = {
    'zh-cn': { local: {
        playerId: '玩家 ID',
        bindUser: '绑定用户',
        setSafe: '设置 safe = {value}',
        bindHint: '填写用户 ID；0 表示解绑当前用户。',
        unbindFirst: '请先在“绑定用户”中填写 0 解绑，再将 safe 设为 false。',
        approveFirst: '请先将 safe 设为 true，再绑定用户。',
        identifier: '标识 / 表达式',
        mode: '匹配模式',
        ignoreCase: '忽略大小写',
        rateLimits: '限流说明',
        limitGroup: '分组',
        matchingOptions: '匹配条件',
        quota: '配额',
        limitHint: '限流按 IP 计算。不同分组的配额独立，同一分组内的所有匹配条件共用配额。分页、排序和用户筛选均在本地进行，不消耗请求配额。',
        matchLimit: '每条标识查询最多允许匹配 1000 条，超过时拒绝查询。符合条件的结果一次性返回。',
        tooManyMatches: '匹配结果超过 1000 条，请缩小查询范围后重试。',
        matchHint: '普通模式按字面匹配；正则使用 MySQL ICU 语法，可用 (?i) 忽略大小写。',
        filterOwner: '筛选归属玩家',
        clearFilter: '清空筛选',
        ownerId: '玩家 #{id}',
        groups: {
            exact: { name: '完整匹配组', matches: '完整匹配，区分大小写' },
            prefix: { name: '前缀匹配组', matches: '前缀匹配，区分大小写' },
            text: { name: '文本匹配组', matches: '包含、后缀（无论是否忽略大小写）；完整匹配、前缀（忽略大小写）' },
            regex: { name: '正则匹配组', matches: '正则表达式（无论是否忽略大小写）' },
        },
        modes: {
            exact: '完整匹配',
            contains: '包含',
            startswith: '前缀',
            endswith: '后缀',
            regex: '正则表达式',
        },
        byPlayer: '查询玩家标识',
        byIdentifier: '查询标识归属',
        owner: '归属玩家',
        empty: '没有找到标识',
        unbound: '未绑定玩家',
    } },
    en: { local: {
        playerId: 'Player ID',
        bindUser: 'Bind user',
        setSafe: 'Set safe = {value}',
        bindHint: 'Enter a user ID; 0 unbinds the current owner.',
        unbindFirst: 'Enter 0 in Bind user to unbind before setting safe to false.',
        approveFirst: 'Set safe to true before binding a user.',
        identifier: 'Identifier / pattern',
        mode: 'Match mode',
        ignoreCase: 'Ignore case',
        rateLimits: 'Rate limits',
        limitGroup: 'Group',
        matchingOptions: 'Matching options',
        quota: 'Quota',
        limitHint: 'Limits apply per IP. Groups have independent quotas; all matching options within a group share its quota. Pagination, sorting and owner filtering run locally without using request quotas.',
        matchLimit: 'Identifier queries matching more than 1000 results are rejected. All matching results are returned in one response.',
        tooManyMatches: 'More than 1000 identifiers match. Please narrow your search and try again.',
        matchHint: 'Plain modes match literal text; regex uses MySQL ICU syntax, with (?i) for case-insensitive matching.',
        filterOwner: 'Filter owner',
        clearFilter: 'Clear',
        ownerId: 'Player #{id}',
        groups: {
            exact: { name: 'Exact group', matches: 'Exact, case-sensitive' },
            prefix: { name: 'Prefix group', matches: 'Prefix, case-sensitive' },
            text: { name: 'Text group', matches: 'Contains and suffix (either case setting); exact and prefix (ignore case)' },
            regex: { name: 'Regex group', matches: 'Regex (either case setting)' },
        },
        modes: {
            exact: 'Exact',
            contains: 'Contains',
            startswith: 'Prefix',
            endswith: 'Suffix',
            regex: 'Regex',
        },
        byPlayer: 'Find player identifiers',
        byIdentifier: 'Find identifier owner',
        owner: 'Owner',
        empty: 'No identifiers found',
        unbound: 'Unbound',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.identifier-query {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.identifier-actions {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-width: 20rem;
}

.binding-form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.query-form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}

.query-form label {
    min-width: 5rem;
}

.query-form .el-input {
    flex: 1 1 12rem;
    max-width: 24rem;
}

.query-form select {
    max-width: 100%;
    min-height: 28px;
    padding: 3px 8px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.query-form select:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

p {
    margin: 0;
}

.rate-limit-details {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 60rem;
    margin: auto;
    text-align: left;
}

.identifier-header {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    white-space: nowrap;
}

.identifier-value {
    font-family: monospace;
    overflow-wrap: anywhere;
}

.owner-filter {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: fit-content;
    max-width: calc(100vw - 2rem);
    padding: 6px;
}

.owner-filter__search {
    width: 100%;
    min-width: 10rem;
}
</style>
