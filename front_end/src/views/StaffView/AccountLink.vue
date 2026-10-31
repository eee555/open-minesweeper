<template>
    <ElForm :model="form">
        <ElFormItem :label="t('prop.userId')">
            <ElInput v-model="form.id" type="number" />
        </ElFormItem>
        <ElFormItem :label="t('accountlink.platform')">
            <ElSelect v-model="form.platform">
                <ElOption v-for="platform of manualAccountLinkPlatforms" :key="platform" :label="t(`platform.${platform}`)" :value="platform" />
            </ElSelect>
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
    <PrDataTable
        v-loading="loading"
        :value="accountLinks"
        row-hover
        size="small"
        paginator
        :rows="10"
        :rows-per-page-options="[10, 25, 50, 100]"
        paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown JumpToPageInput CurrentPageReport"
    >
        <PrColumn field="userprofile" :header="t('prop.userId')" sortable />
        <PrColumn field="platform" :header="t('accountlink.platform')" sortable>
            <template #body="{ data }: { data: AccountLinkQueueItem }">
                {{ t(`platform.${data.platform}`) }}
            </template>
        </PrColumn>
        <PrColumn field="identifier" :header="t('local.platformId')" sortable />
        <PrColumn field="verified" :header="t('accountlink.verified')" sortable>
            <template #body="{ data }: { data: AccountLinkQueueItem }">
                {{ t(data.verified ? 'accountlink.verified' : 'local.unverified') }}
            </template>
        </PrColumn>
    </PrDataTable>
</template>

<script setup lang="ts">
import { ElForm, ElFormItem, ElInput, ElOption, ElSelect, vLoading } from 'element-plus';
import PrColumn from 'primevue/column';
import PrDataTable from 'primevue/datatable';
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import type { AccountLinkPlatform } from '@/utils/accountlinks';
import { manualAccountLinkPlatforms } from '@/utils/accountlinks';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const { proxy } = useCurrentInstance();

interface AccountLinkQueueItem {
    id: number | null;
    platform: AccountLinkPlatform;
    identifier: string;
    userprofile: number;
    verified: boolean;
}

const form = reactive({
    id: 0,
    platform: '',
    identifier: '',
});

const accountLinks = ref<AccountLinkQueueItem[]>([]);
const loading = ref(false);

const refresh = async () => {
    loading.value = true;
    await proxy.$axios.get('/api/accountlink/admin/queue').then((response) => {
        accountLinks.value = response.data;
    }).catch(httpErrorNotification);
    loading.value = false;
};

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
        unverified: '未验证',
    } },
    en: { local: {
        platformId: 'Platform ID',
        unverified: 'Unverified',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
