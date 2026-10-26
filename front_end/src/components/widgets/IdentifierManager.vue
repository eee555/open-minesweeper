<template>
    <!-- 标识管理UI -->
    <!-- 表格第一列显示标识，用等宽字体。最后一行用来输入新的标识。第二列放操作按钮 -->
    <div>
        <IdentifierDisplayOptions />
        <ElTable :data="identifierdata">
            <!-- 标识列 -->
            <ElTableColumn prop="data" sortable>
                <template #default="scope">
                    <!-- 左margin是为了补偿输入框内文本的偏移 -->
                    <ElInput
                        v-if="scope.row.data === ''" v-model="new_identifiers" size="small" style="width: 200px;margin-left: -7px"
                        input-style="font-family: 'Courier New', Courier, monospace;"
                    />
                    <IdentifierText v-else :text="scope.row.data" />
                </template>
            </ElTableColumn>
            <!-- 操作列 -->
            <ElTableColumn>
                <template #default="scope">
                    <!-- 添加标识 -->
                    <BaseTextButton
                        v-if="scope.row.data === ''" underline="never" :aria-label="t('action.addIdentifier')"
                        @click="addIdentifier(new_identifiers)"
                    >
                        <BaseIconAdd />
                    </BaseTextButton>
                    <!-- 复制标识 -->
                    <IconCopy v-else :text="scope.row.data" />
                    &nbsp;
                    <!-- 删除标识 -->
                    <BaseTextButton
                        v-if="user.id == store.user.id && scope.row.data !== ''" underline="never"
                        type="danger" :aria-label="t('local.remove')" @click="delIdentifier(scope.row.data)"
                    >
                        <BaseIconDelete />
                    </BaseTextButton>
                </template>
            </ElTableColumn>
        </ElTable>
    </div>
</template>

<script setup lang="ts">
import { ElInput, ElNotification, ElTable, ElTableColumn } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import IconCopy from './IconCopy.vue';
import IdentifierDisplayOptions from './IdentifierDisplayOptions.vue';
import IdentifierText from './IdentifierText.vue';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconAdd, BaseIconDelete } from '@/components/common/icon';
import { httpErrorNotification, unknownErrorNotification } from '@/components/Notifications';
import { fetchUserIdentifiers } from '@/services/userService';
import { store } from '@/store';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { removeItem } from '@/utils/system/tools';
import { UserProfile } from '@/utils/userprofile';

const emit = defineEmits<{
    identifiersChanged: [];
}>();

const { proxy } = useCurrentInstance();
const new_identifiers = ref('');
const loading = ref(false);

const user = defineModel<UserProfile>('user', {
    type: UserProfile, default: () => new UserProfile(),
});

async function refresh() {
    if (loading.value) return;
    if (user.value.id < 1) return;
    if (user.value.identifiers === undefined) {
        loading.value = true;
        try {
            user.value.identifiers = await fetchUserIdentifiers(user.value.id);
        } catch (error) {
            httpErrorNotification(error);
        }
        loading.value = false;
    }
}

watch(user, refresh, { immediate: true });

const identifierdata = computed(() => {
    const data = user.value.identifiers ? user.value.identifiers.map((value) => ({ data: value })) : [];
    if (user.value.id == store.user.id) data.push({ data: '' });
    return data;
});

function delIdentifier(identifier: string) {
    proxy.$axios.post('identifier/del/', {
        identifier: identifier,
    }).then(function (response) {
        if (user.value.identifiers !== undefined) {
            user.value.identifiers = removeItem(user.value.identifiers, identifier);
        }
        emit('identifiersChanged');
        ElNotification({
            title: t('identifierManager.delIdentifierSuccess'),
            message: t('identifierManager.processedNVideos', [response.data.value]),
            type: 'success',
        });
    }).catch(httpErrorNotification);
}

async function addIdentifier(identifier: string) {
    try {
        const response = await proxy.$axios.post('identifier/add/', {
            identifier: identifier,
        });
        if (response.data.type === 'success') {
            const identifiers = user.value.identifiers ?? [];
            user.value.identifiers = [...identifiers, identifier];
            emit('identifiersChanged');
            ElNotification({
                title: t('identifierManager.addIdentifierSuccess'),
                message: t('identifierManager.processedNVideos', [response.data.value]),
                type: 'success',
            });
            store.new_identifier = false;
        } else if (response.data.category === 'notFound') {
            ElNotification({
                title: t('identifierManager.notFound'),
                type: 'error',
            });
        } else if (response.data.category === 'conflict') {
            ElNotification({
                title: t('identifierManager.conflict'),
                message: t('identifierManager.ownedBy', [response.data.value]),
                type: 'error',
            });
        } else {
            unknownErrorNotification(response.data);
        }
        new_identifiers.value = '';
    } catch (error) {
        httpErrorNotification(error);
    }
}

const i18nMessages = {
    'zh-cn': { local: { remove: '删除标识' } },
    en: { local: { remove: 'Delete identifier' } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
::v-deep(.el-table .el-table__cell) {
    font-family: 'Courier New', Courier, monospace;
    font-size: 12px;
    padding: 0;
    margin: 0;
}
</style>
