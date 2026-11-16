<template>
    <ElForm :model="form">
        <ElFormItem :label="t('prop.userId')">
            <ElInput v-model="form.id" type="number" />
        </ElFormItem>
        <ElFormItem :label="t('accountlink.platform')">
            <select v-model="form.platform" class="base-select" style="width: 100%" :aria-label="t('accountlink.platform')">
                <option disabled value="">
                    {{ t('local.selectPlatform') }}
                </option>
                <option v-for="platform of manualAccountLinkPlatforms" :key="platform" :value="platform">
                    {{ t(`platform.${platform}`) }}
                </option>
            </select>
        </ElFormItem>
        <ElFormItem :label="t('local.platformId')">
            <ElInput v-model="form.identifier" />
        </ElFormItem>
        <ElFormItem>
            <BaseButton @click="verify">
                {{ t('button.link') }}
            </BaseButton>
            <BaseButton @click="unverify">
                {{ t('button.unlink') }}
            </BaseButton>
        </ElFormItem>
    </ElForm>
    <div v-loading="loading" class="account-link-queue">
        <div class="account-link-queue__filters">
            <label class="account-link-queue__field">
                <span>{{ t('accountlink.platform') }}</span>
                <select v-model="platformFilter" class="base-select base-select--small" :aria-label="t('local.filterPlatform')" data-cy="filter-platform">
                    <option value="">{{ t('all') }}</option>
                    <option v-for="platform of AccountLinkPlatform" :key="platform" :value="platform">
                        {{ t(`platform.${platform}`) }}
                    </option>
                </select>
            </label>
            <label class="account-link-queue__field">
                <span>{{ t('accountlink.verified') }}</span>
                <select v-model="verifiedFilter" class="base-select base-select--small" :aria-label="t('local.filterVerified')" data-cy="filter-verified">
                    <option value="">{{ t('all') }}</option>
                    <option value="true">{{ t('accountlink.verified') }}</option>
                    <option value="false">{{ t('local.unverified') }}</option>
                </select>
            </label>
        </div>
        <BaseTable :empty="accountLinks.length === 0" :empty-text="t('local.empty')" :column-count="4" data-cy="account-link-table">
            <template #head>
                <tr>
                    <th scope="col" :aria-sort="sortState(sortOrder)" data-cy="header-user-id">
                        <BaseButton size="small" text :aria-label="t('prop.userId')" data-cy="sort-user-id" @click="toggleSort">
                            {{ t('prop.userId') }}
                            <SortIcon :state="sortState(sortOrder)" />
                        </BaseButton>
                    </th>
                    <th scope="col">
                        {{ t('accountlink.platform') }}
                    </th>
                    <th scope="col">
                        {{ t('local.platformId') }}
                    </th>
                    <th scope="col">
                        {{ t('accountlink.verified') }}
                    </th>
                </tr>
            </template>
            <tr v-for="link in accountLinks" :key="link.id">
                <td>{{ link.userprofile }}</td>
                <td>{{ t(`platform.${link.platform}`) }}</td>
                <td>{{ link.identifier }}</td>
                <td>{{ t(link.verified ? 'accountlink.verified' : 'local.unverified') }}</td>
            </tr>
        </BaseTable>
        <BasePagination
            v-model:current-start="currentStart" v-model:page-size="pageSize"
            :total="total" :page-size-options="[10, 25, 50, 100]" :disabled="loading"
            data-cy="account-link-pagination" @change="handlePageChange"
        />
    </div>
</template>

<script setup lang="ts">
import { ElForm, ElFormItem, ElInput, vLoading } from 'element-plus';
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
import { httpErrorNotification } from '@/components/Notifications';
import { AccountLinkPlatform, manualAccountLinkPlatforms } from '@/utils/accountlinks';
import type { AccountLinkQueuePageResponse, AccountLinkQueueResponse } from '@/utils/accountlinks/common';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const { proxy } = useCurrentInstance();

const form = reactive({
    id: 0,
    platform: '',
    identifier: '',
});

const accountLinks = ref<AccountLinkQueueResponse[]>([]);
const loading = ref(false);
const total = ref(0);
const currentStart = ref(1);
const pageSize = ref(10);
const platformFilter = ref('');
const verifiedFilter = ref('');
const sortOrder = ref<number | undefined>(undefined);
const orderParam = computed(() => {
    if (sortOrder.value === undefined) return '';
    return sortOrder.value > 0 ? 'asc' : 'desc';
});

const refresh = async () => {
    loading.value = true;
    const page = Math.floor((currentStart.value - 1) / pageSize.value) + 1;
    const params: Record<string, string | number> = {
        page, page_size: pageSize.value, platform: platformFilter.value, order: orderParam.value,
    };
    if (verifiedFilter.value !== '') params.verified = verifiedFilter.value;
    try {
        const response = await proxy.$axios.get<AccountLinkQueuePageResponse>('/api/accountlink/admin/queue', { params });
        const { count, items } = response.data;
        total.value = count;
        accountLinks.value = items;
        const lastPage = Math.max(1, Math.ceil(count / pageSize.value));
        if (count > 0 && page > lastPage) {
            currentStart.value = (lastPage - 1) * pageSize.value + 1;
            void refresh();
            return;
        }
    } catch (error) {
        httpErrorNotification(error);
    }
    loading.value = false;
};

function handlePageChange() {
    void refresh();
}

function handleFilterChange() {
    currentStart.value = 1;
    void refresh();
}

watch([platformFilter, verifiedFilter], handleFilterChange);

function toggleSort() {
    sortOrder.value = nextSortOrder(sortOrder.value, true, undefined);
    currentStart.value = 1;
    void refresh();
}

function verify() {
    proxy.$axios.post('/api/accountlink/verify/', {
        id: form.id,
        platform: form.platform,
        identifier: form.identifier,
    }).then(function () {
        form.id = 0;
        form.platform = '';
        form.identifier = '';
        void refresh();
    }).catch(httpErrorNotification);
}

function unverify() {
    proxy.$axios.post('/api/accountlink/unverify/', {
        id: form.id,
        platform: form.platform,
        identifier: form.identifier,
    }).then(function () {
        form.id = 0;
        form.platform = '';
        form.identifier = '';
        void refresh();
    }).catch(httpErrorNotification);
}

onMounted(refresh);

const i18nMessages = {
    'zh-cn': { local: {
        platformId: '平台 ID',
        selectPlatform: '选择平台',
        unverified: '未验证',
        empty: '暂无关联记录',
        filterPlatform: '筛选平台',
        filterVerified: '筛选验证状态',
    } },
    en: { local: {
        platformId: 'Platform ID',
        selectPlatform: 'Select a platform',
        unverified: 'Unverified',
        empty: 'No account links',
        filterPlatform: 'Filter platform',
        filterVerified: 'Filter verification',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.account-link-queue__filters {
    display: flex;
    align-items: center;
    gap: 0.5em;
    margin: 0.5em 0;
}
.account-link-queue__field {
    display: inline-flex;
    align-items: center;
    gap: 0.25em;
    white-space: nowrap;
}
</style>
