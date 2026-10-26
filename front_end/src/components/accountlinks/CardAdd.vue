<template>
    <ElButton style="height: 100%; align-items: center;" plain @click="formvisible = true">
        <BaseIconAdd />
    </ElButton>

    <ElDialog v-model="formvisible" :title="t('accountlink.addLink')" width="25rem">
        <ElForm :model="form">
            <ElFormItem :label="t('accountlink.platform')">
                <ElSelect v-model="form.platform">
                    <ElOption
                        v-for="platform of manualAccountLinkPlatforms" :key="platform" :value="platform" :label="t(`common.platform.${platform}`)"
                        :disabled="userHasPlatform(platform)"
                    />
                </ElSelect>
            </ElFormItem>
            <ElFormItem label="ID">
                <ElInput v-model="form.identifier" maxlength="128" />
            </ElFormItem>
            <ElFormItem v-if="form.platform">
                <AccountLinkGuide :platform="form.platform" />
            </ElFormItem>
        </ElForm>
        <template #footer>
            <BaseButtonCancel @click="formvisible = false" />
            <BaseButtonConfirm :disabled="!formValid" @click="submit" />
        </template>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElOption, ElSelect } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import AccountLinkGuide from './Guide.vue';

import BaseButtonCancel from '@/components/common/BaseButtonCancel.vue';
import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';
import { BaseIconAdd } from '@/components/common/icon';
import { AccountLinks, manualAccountLinkPlatforms } from '@/utils/accountlinks';
import type { AccountLinkPlatform } from '@/utils/accountlinks';

const props = defineProps({
    accountlinks: { type: AccountLinks, default: () => new AccountLinks() },
});

const emit = defineEmits<{
    addLink: [platform: AccountLinkPlatform, identifier: string];
}>();

const { t } = useI18n();

const formvisible = ref(false);
const form = ref<{ platform: '' | AccountLinkPlatform; identifier: string }>({
    platform: '',
    identifier: '',
});

watch(formvisible, (visible) => {
    if (!visible) resetForm();
});

const formValid = computed(() => {
    switch (form.value.platform) {
        case 'B':
        case 'a':
        case 'c':
        case 'q':
        case 'w': {
            const num = parseInt(form.value.identifier, 10);
            return !isNaN(num) && num.toString() === form.value.identifier && num > 0;
        }
        default:
            return false;
    }
});

function userHasPlatform(platform: AccountLinkPlatform) {
    return props.accountlinks.has(platform);
}

function resetForm() {
    form.value.platform = '';
    form.value.identifier = '';
}

function submit() {
    if (form.value.platform === '') return;
    emit('addLink', form.value.platform, form.value.identifier);
    formvisible.value = false;
}
</script>
