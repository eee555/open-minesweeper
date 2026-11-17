<template>
    <div class="video-query">
        <div class="video-query__panels">
            <section class="card video-query__panel" :aria-label="t('button.filter')">
                <h2 class="card-title video-query__title">
                    {{ t('button.filter') }}<span class="text-secondary text-small video-query__title-hint">{{ t('local.filterHint') }}</span>
                </h2>
                <div class="video-query__tags">
                    <div v-for="(tag, index) in filterTags" :key="tag.id" class="query-tag" data-cy="filter-tag">
                        <select v-model="tag.field" class="base-select base-select--small query-tag__field" data-cy="field-select" :aria-label="t('local.field')" @change="resetFilter(tag)">
                            <optgroup v-for="group in filterGroupsFor(tag)" :key="group.label" :label="t(group.label)">
                                <option v-for="field in group.fields" :key="field.key" :value="field.key">
                                    {{ t(field.label) }}
                                </option>
                            </optgroup>
                        </select>
                        <div v-if="fieldKind(tag.field) === 'enum'" class="checkbox-buttons checkbox-buttons--compact query-tag__enum">
                            <label v-for="option in enumOptions[tag.field]" :key="option.value" class="checkbox-button" data-cy="enum-option" :title="t(option.label)" :aria-label="t(option.label)">
                                <input v-model="tag.selected" class="checkbox-button-input" type="checkbox" :value="option.value">
                                <span class="checkbox-button-content">
                                    <VideoStateIcon v-if="tag.field === 'state'" :state="asState(option.value)" />
                                    <SoftwareIcon v-else-if="tag.field === 'software'" :software="asSoftware(option.value)" />
                                    <span v-else>{{ t(option.label) }}</span>
                                </span>
                            </label>
                        </div>
                        <span v-else class="query-tag__range">
                            <button class="query-tag__bracket" type="button" data-cy="lower-bracket" :aria-pressed="tag.lowerInclusive" :aria-label="t('local.lowerBound')" :title="t('local.bracketHint')" @click="tag.lowerInclusive = !tag.lowerInclusive">
                                {{ lowerBracket(tag) }}
                            </button>
                            <input v-model="tag.lower" class="query-tag__bound" data-cy="lower-bound" :type="inputType(tag)" :disabled="stnbBlocked(tag)" placeholder="-∞" :aria-label="t('local.lowerBound')" :title="t('local.negativeInfinity')">
                            <span class="query-tag__separator">,</span>
                            <input v-model="tag.upper" class="query-tag__bound" data-cy="upper-bound" :type="inputType(tag)" :disabled="stnbBlocked(tag)" placeholder="+∞" :aria-label="t('local.upperBound')" :title="t('local.positiveInfinity')">
                            <button class="query-tag__bracket" type="button" data-cy="upper-bracket" :aria-pressed="tag.upperInclusive" :aria-label="t('local.upperBound')" :title="t('local.bracketHint')" @click="tag.upperInclusive = !tag.upperInclusive">
                                {{ upperBracket(tag) }}
                            </button>
                        </span>
                        <span v-if="isDerived(tag.field)" class="query-tag__derived" data-cy="derived" :title="t('local.derivedHint')">{{ t('local.derived') }}</span>
                        <span v-if="stnbBlocked(tag)" class="query-tag__warning" data-cy="stnb-hint">{{ t('local.stnbHint') }}</span>
                        <button class="query-tag__icon" type="button" :aria-label="t('local.remove')" data-cy="remove-tag" @click="removeFilter(index)">
                            <i class="pi pi-times" aria-hidden="true" />
                        </button>
                    </div>
                    <BaseButton size="small" data-cy="add-filter" @click="addFilter">
                        <template #icon>
                            <i class="pi pi-plus" aria-hidden="true" />
                        </template>{{ t('local.addFilter') }}
                    </BaseButton>
                </div>
                <p v-if="filterTags.length === 0" class="text-secondary text-small video-query__hint">
                    {{ t('local.noFilters') }}
                </p>
            </section>

            <section class="card video-query__panel" :aria-label="t('button.sort')">
                <h2 class="card-title video-query__title">
                    {{ t('button.sort') }}<span class="text-secondary text-small video-query__title-hint">{{ t('local.sortHint') }}</span>
                </h2>
                <div class="video-query__tags">
                    <div v-for="(rule, index) in sortRules" :key="rule.id" class="query-tag" data-cy="sort-tag">
                        <span class="query-tag__index" :aria-label="t('local.priority', { index: index + 1 })">{{ index + 1 }}</span>
                        <select v-model="rule.field" class="base-select base-select--small query-tag__field" :aria-label="t('local.field')">
                            <optgroup v-for="group in sortGroupsFor(rule)" :key="group.label" :label="t(group.label)">
                                <option v-for="field in group.fields" :key="field.key" :value="field.key">
                                    {{ t(field.label) }}
                                </option>
                            </optgroup>
                        </select>
                        <BaseButton class="square-button" size="small" :aria-label="t(sortDirectionLabel(rule))" :title="t(sortDirectionLabel(rule))" data-cy="sort-direction" @click="toggleSortDirection(rule)">
                            <template #icon>
                                <i :class="sortDirectionIcon(rule)" aria-hidden="true" />
                            </template>
                        </BaseButton>
                        <BaseButton class="square-button" size="small" :disabled="index === 0" :aria-label="t('local.moveUp')" data-cy="move-up" @click="moveSort(index, -1)">
                            <template #icon>
                                <i class="pi pi-angle-up" aria-hidden="true" />
                            </template>
                        </BaseButton>
                        <BaseButton class="square-button" size="small" :disabled="index === sortRules.length - 1" :aria-label="t('local.moveDown')" data-cy="move-down" @click="moveSort(index, 1)">
                            <template #icon>
                                <i class="pi pi-angle-down" aria-hidden="true" />
                            </template>
                        </BaseButton>
                        <button class="query-tag__icon" type="button" :aria-label="t('local.remove')" data-cy="remove-tag" @click="removeSort(index)">
                            <i class="pi pi-times" aria-hidden="true" />
                        </button>
                    </div>
                    <BaseButton size="small" data-cy="add-sort" @click="addSort">
                        <template #icon>
                            <i class="pi pi-plus" aria-hidden="true" />
                        </template>{{ t('local.addSort') }}
                    </BaseButton>
                </div>
                <p v-if="sortRules.length === 0" class="text-secondary text-small video-query__hint">
                    {{ t('local.noSorts') }}
                </p>
            </section>
        </div>

        <section class="card video-query__panel" :aria-label="t('local.pagination')">
            <div class="card-title video-query__title">
                <label class="video-query__control">
                    <span>{{ t('local.perPage') }}</span>
                    <select v-model.number="pageSize" class="base-select base-select--small" data-cy="page-size" :aria-label="t('local.perPage')">
                        <option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option>
                    </select>
                </label>
                <span class="video-query__limit">{{ t('local.limit', { count: RESULT_LIMIT }) }}</span>
                <span v-if="loading" class="text-secondary text-small" data-cy="query-loading">{{ t('local.loading') }}</span>
                <span v-if="queryFailed" class="text-secondary text-small" data-cy="query-error">{{ t('local.queryFailed') }}</span>
            </div>
            <div class="video-query__pager">
                <div class="button-group video-query__pages" data-cy="page-buttons">
                    <BaseButton class="square-button" size="small" :disabled="currentPage === 1" :aria-label="t('local.prev')" data-cy="page-prev" @click="goToPage(currentPage - 1)">
                        <template #icon>
                            <i class="pi pi-angle-left" aria-hidden="true" />
                        </template>
                    </BaseButton>
                    <BaseButton v-for="page in allPages" :key="page" size="small" :type="pageButtonType(page)" :aria-current="pageAriaCurrent(page)" data-cy="page-button" @click="goToPage(page)">
                        {{ pageLabel(page) }}
                    </BaseButton>
                    <BaseButton class="square-button" size="small" :disabled="currentPage >= pageCount" :aria-label="t('local.next')" data-cy="page-next" @click="goToPage(currentPage + 1)">
                        <template #icon>
                            <i class="pi pi-angle-right" aria-hidden="true" />
                        </template>
                    </BaseButton>
                </div>
            </div>
        </section>

        <div class="video-query__table-bar" data-cy="column-selector">
            <MultiSelector v-model="selectedColumns" :options="ColumnChoices" :labels="columnLabels" />
        </div>
        <VideoList v-loading="loading" class="video-query__table" :videos="pageRows" :columns="videoColumns" display-only />
    </div>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import 'primeicons/primeicons.css';

import { vLoading } from 'element-plus';
import { computed, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import VideoList from '@/components/VideoList/App.vue';
import MultiSelector from '@/components/widgets/MultiSelector.vue';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import VideoStateIcon from '@/components/widgets/VideoStateIcon.vue';
import { fetchVideoQuery } from '@/services/videoService';
import type { VideoQueryFilter, VideoQuerySort } from '@/services/videoService';
import { VideoListConfig } from '@/store';
import { ColumnChoices } from '@/utils/ms_const';
import type { ColumnChoice, MS_Software, MS_State } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

type FieldKind = 'enum' | 'number' | 'datetime';
type SortDirection = 'asc' | 'desc';

interface FieldOption {
    key: string;
    label: string;
}

interface FieldGroup {
    label: string;
    fields: FieldOption[];
}

interface EnumOption {
    value: string;
    label: string;
}

interface FilterTag {
    id: number;
    field: string;
    selected: string[];
    lower: string;
    upper: string;
    lowerInclusive: boolean;
    upperInclusive: boolean;
}

interface SortRule {
    id: number;
    field: string;
    direction: SortDirection;
}

const RESULT_LIMIT = 1000;
const pageSizes = [20, 50, 100];
const enumFields = ['state', 'software', 'level', 'mode'];
const datetimeFields = ['upload_time', 'end_time'];

const numberFields = [
    'file_size', 'stored_file_size', 'upload_time', 'end_time', 'timems', 'bv', 'bvs',
    'left', 'right', 'double', 'cl', 'left_ce', 'right_ce', 'double_ce', 'ce',
    'left_s', 'right_s', 'double_s', 'cl_s', 'left_ces', 'right_ces', 'double_ces', 'ce_s',
    'path', 'pluck', 'flag', 'op', 'isl', 'flag_s', 'ioe', 'thrp', 'corr',
    'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8',
];

const enumOptions: Record<string, EnumOption[]> = {
    state: [
        { value: 'a', label: 'state.a' },
        { value: 'b', label: 'state.b' },
        { value: 'c', label: 'state.c' },
        { value: 'd', label: 'state.d' },
    ],
    software: [
        { value: 'e', label: 'software.e' },
        { value: 'a', label: 'software.a' },
        { value: 'r', label: 'software.r' },
        { value: 'm', label: 'software.m' },
        { value: 'x', label: 'software.x' },
    ],
    level: [
        { value: 'b', label: 'level.b' },
        { value: 'i', label: 'level.i' },
        { value: 'e', label: 'level.e' },
    ],
    mode: [
        { value: '00', label: 'mode.code00' },
        { value: '05', label: 'mode.code05' },
        { value: '06', label: 'mode.code06' },
        { value: '10', label: 'mode.code10' },
    ],
};

const fieldGroups: FieldGroup[] = [
    { label: 'local.groupEnum',
        fields: [
            { key: 'state', label: 'prop.state' },
            { key: 'software', label: 'prop.software' },
            { key: 'level', label: 'prop.level' },
            { key: 'mode', label: 'prop.mode' },
        ] },
    { label: 'local.groupNumber',
        fields: numberFields.map((key) => ({ key, label: `prop.${key}` })) },
    { label: 'local.groupDerived',
        fields: [{ key: 'stnb', label: 'prop.stnb' }] },
    { label: 'local.groupIdentity',
        fields: [{ key: 'id', label: 'prop.videoId' }] },
];

const sortableKeys = ['id', 'level', 'mode', 'state', 'timems', 'bv', 'bvs', 'thrp', 'stnb'];
const sortFieldGroups: FieldGroup[] = [
    { label: 'local.groupEnum', fields: fieldGroups[0].fields.filter((field) => sortableKeys.includes(field.key)) },
    { label: 'local.groupNumber', fields: fieldGroups[1].fields.filter((field) => sortableKeys.includes(field.key)) },
    { label: 'local.groupDerived', fields: [{ key: 'stnb', label: 'prop.stnb' }] },
    { label: 'local.groupIdentity', fields: [{ key: 'id', label: 'prop.videoId' }] },
];

function emptyFilter(id: number, field: string): FilterTag {
    return { id, field, selected: [], lower: '', upper: '', lowerInclusive: true, upperInclusive: false };
}

const filterTags = ref<FilterTag[]>([
    { ...emptyFilter(1, 'state'), selected: ['c', 'a'] },
    { ...emptyFilter(2, 'bv'), lower: '100' },
]);
const sortRules = ref<SortRule[]>([
    { id: 3, field: 'timems', direction: 'asc' },
    { id: 4, field: 'bv', direction: 'desc' },
]);
let nextTagId = 5;

const selectedColumns = computed<string[]>({
    get: () => VideoListConfig.value.query,
    set: (value) => {
        VideoListConfig.value.query = value as ColumnChoice[];
    },
});
const videoColumns = computed<ColumnChoice[]>(() => ColumnChoices.filter((choice) => selectedColumns.value.includes(choice)));

const resultRows = ref<VideoAbstract[]>([]);
const loading = ref(false);
const queryFailed = ref(false);
const pageSize = ref<number>(20);
const currentPage = ref<number>(1);
const pageCount = computed(() => Math.max(1, Math.ceil(resultRows.value.length / pageSize.value)));
const allPages = computed(() => Array.from({ length: pageCount.value }, (_, index) => index + 1));
const firstIndex = computed(() => (currentPage.value - 1) * pageSize.value);
const lastIndex = computed(() => Math.min(firstIndex.value + pageSize.value, resultRows.value.length));
const pageRows = computed(() => resultRows.value.slice(firstIndex.value, lastIndex.value));

watch(pageSize, () => {
    currentPage.value = 1;
});

function asState(value: string): MS_State {
    return value as MS_State;
}

function asSoftware(value: string): MS_Software {
    return value as MS_Software;
}

function fieldKind(field: string): FieldKind {
    if (enumFields.includes(field)) return 'enum';
    return datetimeFields.includes(field) ? 'datetime' : 'number';
}

function isDerived(field: string): boolean {
    return field === 'stnb';
}

function inputType(tag: FilterTag): string {
    return fieldKind(tag.field) === 'datetime' ? 'datetime-local' : 'text';
}

const stnbAllowed = computed(() => {
    const level = filterTags.value.find((tag) => tag.field === 'level');
    return level?.selected.length === 1 && ['b', 'i', 'e'].includes(level.selected[0]);
});

function stnbBlocked(tag: FilterTag): boolean {
    return isDerived(tag.field) && !stnbAllowed.value;
}

function filterGroupsFor(tag: FilterTag): FieldGroup[] {
    const used = new Set(filterTags.value.filter((item) => item.id !== tag.id).map((item) => item.field));
    return fieldGroups.map((group) => ({ ...group, fields: group.fields.filter((field) => !used.has(field.key)) })).filter((group) => group.fields.length > 0);
}

function sortGroupsFor(rule: SortRule): FieldGroup[] {
    const used = new Set(sortRules.value.filter((item) => item.id !== rule.id).map((item) => item.field));
    return sortFieldGroups.map((group) => ({ ...group, fields: group.fields.filter((field) => !used.has(field.key)) })).filter((group) => group.fields.length > 0);
}

function lowerBracket(tag: FilterTag): string {
    return tag.lowerInclusive ? '[' : '(';
}

function upperBracket(tag: FilterTag): string {
    return tag.upperInclusive ? ']' : ')';
}

function resetFilter(tag: FilterTag): void {
    tag.selected = [];
    tag.lower = '';
    tag.upper = '';
    tag.lowerInclusive = true;
    tag.upperInclusive = false;
}

function addFilter(): void {
    const used = new Set(filterTags.value.map((tag) => tag.field));
    const available = fieldGroups.flatMap((group) => group.fields).find((field) => !used.has(field.key));
    if (available === undefined) return;
    filterTags.value.push(emptyFilter(nextTagId++, available.key));
}

function removeFilter(index: number): void {
    filterTags.value.splice(index, 1);
}

function addSort(): void {
    const used = new Set(sortRules.value.map((rule) => rule.field));
    const available = sortFieldGroups.flatMap((group) => group.fields).find((field) => !used.has(field.key));
    if (available === undefined) return;
    sortRules.value.push({ id: nextTagId++, field: available.key, direction: 'asc' });
}

function removeSort(index: number): void {
    sortRules.value.splice(index, 1);
}

function moveSort(index: number, delta: number): void {
    const target = index + delta;
    if (target < 0 || target >= sortRules.value.length) return;
    const [rule] = sortRules.value.splice(index, 1);
    sortRules.value.splice(target, 0, rule);
}

function toggleSortDirection(rule: SortRule): void {
    rule.direction = rule.direction === 'asc' ? 'desc' : 'asc';
}

function sortDirectionIcon(rule: SortRule): string {
    return rule.direction === 'asc' ? 'pi pi-arrow-up' : 'pi pi-arrow-down';
}

function sortDirectionLabel(rule: SortRule): string {
    return rule.direction === 'asc' ? 'button.sortAsc' : 'button.sortDesc';
}

function pageLabel(page: number): string {
    if (resultRows.value.length === 0) return '0-0';
    const first = (page - 1) * pageSize.value;
    const last = Math.min(first + pageSize.value, resultRows.value.length);
    return `${first + 1}-${last}`;
}

function pageButtonType(page: number): 'primary' | 'default' {
    return page === currentPage.value ? 'primary' : 'default';
}

function pageAriaCurrent(page: number): 'page' | undefined {
    return page === currentPage.value ? 'page' : undefined;
}

function goToPage(page: number): void {
    if (page >= 1 && page <= pageCount.value) currentPage.value = page;
}

function parseBound(tag: FilterTag, value: string): string | number | undefined {
    const text = value.trim();
    if (text === '') return undefined;
    if (fieldKind(tag.field) === 'datetime') {
        const date = new Date(text);
        return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
    }
    const number = Number(text);
    return Number.isFinite(number) ? number : undefined;
}

function buildFilters(): VideoQueryFilter[] {
    return filterTags.value.flatMap((tag): VideoQueryFilter[] => {
        if (stnbBlocked(tag)) return [];
        if (fieldKind(tag.field) === 'enum') return tag.selected.length > 0 ? [{ field: tag.field, in: tag.selected }] : [];
        const condition: VideoQueryFilter = { field: tag.field };
        const lower = parseBound(tag, tag.lower);
        const upper = parseBound(tag, tag.upper);
        if (lower !== undefined) condition[tag.lowerInclusive ? 'gte' : 'gt'] = lower;
        if (upper !== undefined) condition[tag.upperInclusive ? 'lte' : 'lt'] = upper;
        return lower !== undefined || upper !== undefined ? [condition] : [];
    });
}

function buildSorts(): VideoQuerySort[] {
    return sortRules.value.filter((rule) => rule.field !== 'stnb' || stnbAllowed.value).map((rule) => ({ field: rule.field, direction: rule.direction }));
}

interface QueryState {
    filters: FilterTag[];
    sorts: SortRule[];
    page: number;
    ps: number;
}

function syncUrl(): void {
    if (window.top !== window) return;
    try {
        const state: QueryState = {
            filters: filterTags.value.map((tag) => ({ ...tag, selected: [...tag.selected] })),
            sorts: sortRules.value.map((rule) => ({ ...rule })),
            page: currentPage.value,
            ps: pageSize.value,
        };
        const url = new URL(window.location.href);
        url.searchParams.set('q', JSON.stringify(state));
        window.history.replaceState(null, '', url.toString());
    } catch {
        return;
    }
}

function restoreUrl(): void {
    try {
        const raw = new URLSearchParams(window.location.search).get('q');
        if (raw === null) return;
        const state = JSON.parse(raw) as QueryState;
        if (!Array.isArray(state.filters) || !Array.isArray(state.sorts)) return;
        filterTags.value = state.filters;
        sortRules.value = state.sorts;
        nextTagId = Math.max(0, ...filterTags.value.map((tag) => tag.id), ...sortRules.value.map((rule) => rule.id)) + 1;
        if (pageSizes.includes(state.ps)) pageSize.value = state.ps;
        if (Number.isInteger(state.page) && state.page >= 1) currentPage.value = state.page;
    } catch {
        return;
    }
}

const QUERY_DEBOUNCE_MS = 5000;
let debounceTimer: ReturnType<typeof setTimeout> | undefined;
let controller: AbortController | undefined;
let revision = 0;

async function runQuery(): Promise<void> {
    controller?.abort();
    controller = new AbortController();
    const current = ++revision;
    loading.value = true;
    queryFailed.value = false;
    syncUrl();
    try {
        const rows = await fetchVideoQuery(buildFilters(), buildSorts(), controller.signal);
        if (current !== revision) return;
        resultRows.value = rows;
        currentPage.value = 1;
    } catch {
        if (current !== revision) return;
        resultRows.value = [];
        queryFailed.value = true;
    } finally {
        if (current === revision) loading.value = false;
    }
}

function scheduleQuery(): void {
    loading.value = true;
    queryFailed.value = false;
    if (debounceTimer !== undefined) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        void runQuery();
    }, QUERY_DEBOUNCE_MS);
}

restoreUrl();
watch([filterTags, sortRules], () => {
    scheduleQuery();
}, { deep: true });
watch([pageSize, currentPage], () => {
    syncUrl();
});
onUnmounted(() => {
    if (debounceTimer !== undefined) clearTimeout(debounceTimer);
    controller?.abort();
});
void runQuery();

const i18nMessages = {
    'zh-cn': { local: {
        filterHint: '枚举字段多选；数值字段用区间，括号可切换开闭，留空表示无穷',
        sortHint: '按标签编号依次排序',
        pagination: '分页',
        field: '字段',
        priority: '第 {index} 优先',
        remove: '删除',
        addFilter: '添加条件',
        addSort: '添加排序',
        noFilters: '暂无筛选条件',
        noSorts: '暂无排序规则',
        perPage: '每页',
        prev: '上一页',
        next: '下一页',
        limit: '每次查询最多返回前 {count} 条',
        loading: '查询中…',
        queryFailed: '查询失败，请稍后重试',
        groupEnum: '枚举字段（多选）',
        groupNumber: '数值 / 时间字段（区间）',
        groupDerived: '派生数值字段',
        groupIdentity: '标识字段',
        lowerBound: '下限',
        upperBound: '上限',
        bracketHint: '点击切换开区间 / 闭区间',
        negativeInfinity: '负无穷：留空表示无下界',
        positiveInfinity: '正无穷：留空表示无上界',
        derived: '派生',
        derivedHint: 'STNB 按等级系数换算，不是可直接查询的字段',
        stnbHint: '需先将等级筛选为单个级别',
    } },
    en: { local: {
        filterHint: 'Enums use multi-select; numbers use intervals with toggleable brackets',
        sortHint: 'Sort by tag order, from left to right',
        pagination: 'Pagination',
        field: 'Field',
        priority: 'Priority {index}',
        remove: 'Remove',
        addFilter: 'Add condition',
        addSort: 'Add sort',
        noFilters: 'No filters yet',
        noSorts: 'No sort rules yet',
        perPage: 'Per page',
        prev: 'Previous',
        next: 'Next',
        limit: 'At most the first {count} rows per query',
        loading: 'Loading…',
        queryFailed: 'Query failed, please retry later',
        groupEnum: 'Enums (multi-select)',
        groupNumber: 'Numbers and times (interval)',
        groupDerived: 'Derived numbers',
        groupIdentity: 'Identifiers',
        lowerBound: 'Lower bound',
        upperBound: 'Upper bound',
        bracketHint: 'Click to toggle open / closed interval',
        negativeInfinity: 'Negative infinity: leave empty for no lower bound',
        positiveInfinity: 'Positive infinity: leave empty for no upper bound',
        derived: 'Derived',
        derivedHint: 'STNB is derived from the level coefficient, not a directly queryable column',
        stnbHint: 'Select exactly one level before using STNB',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const columnLabels = computed(() => ColumnChoices.map((key) => t(`prop.${key}`)));
</script>

<style scoped>
.video-query {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
}

.video-query__panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr));
    gap: 8px;
    min-width: 0;
}

.video-query__panel {
    overflow: visible;
    padding: 8px;
}

.video-query__title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
    padding-bottom: 4px;
    font-size: var(--ui-font-size-base);
}

.video-query__title-hint {
    font-weight: 400;
}

.video-query__tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
}

.query-tag {
    display: inline-flex;
    box-sizing: border-box;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    max-width: 100%;
    padding: 3px 4px;
    border: 1px solid var(--ui-border-color);
    border-inline-start: 3px solid var(--ui-color-primary-light-5);
    background: var(--ui-fill-color-light);
    color: var(--ui-text-color-regular);
    font-size: var(--ui-font-size-extra-small);
    line-height: 1.4;
}

.query-tag__field {
    min-width: 6em;
    max-width: 12em;
}

.query-tag__enum {
    max-width: 18em;
}

.query-tag__enum .checkbox-button-content {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
}

.query-tag__range {
    display: inline-flex;
    align-items: center;
    gap: 2px;
}

.query-tag__bracket {
    box-sizing: border-box;
    min-width: 14px;
    height: 24px;
    margin: 0;
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--ui-color-primary);
    font-family: monospace;
    font-size: var(--ui-font-size-medium);
    cursor: pointer;
}

.query-tag__bracket:hover {
    color: var(--ui-color-primary-dark-2);
}

.query-tag__bracket:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

.query-tag__bound {
    box-sizing: border-box;
    width: fit-content;
    min-width: 3em;
    max-width: 12em;
    height: 24px;
    field-sizing: content;
    margin: 0;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    padding: 2px 4px;
    background: var(--ui-fill-color-blank);
    color: var(--ui-text-color-regular);
    font-family: inherit;
    font-size: var(--ui-font-size-extra-small);
    line-height: 1.4;
}

.query-tag__bound:focus {
    border-color: var(--ui-color-primary);
    outline: none;
}

.query-tag__separator {
    color: var(--ui-text-color-secondary);
}

.query-tag__derived {
    border: 1px solid var(--ui-color-warning-light-5);
    padding: 0 4px;
    color: var(--ui-color-warning);
    cursor: help;
}

.query-tag__warning {
    color: var(--ui-color-warning);
    font-size: var(--ui-font-size-extra-small);
}

.query-tag__index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.6em;
    height: 1.6em;
    background: var(--ui-color-primary-light-9);
    color: var(--ui-color-primary);
    font-weight: 600;
}

.query-tag__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    margin: 0;
    border: 0;
    padding: 0;
    background: transparent;
    color: var(--ui-text-color-secondary);
    font-size: 11px;
    cursor: pointer;
}

.query-tag__icon:hover {
    color: var(--ui-color-danger);
}

.query-tag__icon:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

.video-query__hint {
    margin: 6px 0 0;
}

.video-query__limit {
    border: 1px solid var(--ui-color-warning-light-5);
    padding: 1px 5px;
    color: var(--ui-color-warning);
    font-size: var(--ui-font-size-extra-small);
    font-weight: 400;
}

.video-query__pager {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}

.video-query__control {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.video-query__pages {
    flex-wrap: wrap;
    max-width: 100%;
    row-gap: 4px;
}

.video-query__table-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
}

.video-query__table {
    margin-top: 2px;
    overflow-x: auto;
}
</style>
