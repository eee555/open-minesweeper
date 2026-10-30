<template>
    <span v-if="id === 0">
        请输入非零届数
    </span>
    <span v-else-if="notFound">
        未找到该届信息
        <BaseButton @click="createGSC">
            创建比赛
        </BaseButton>
    </span>
    <span v-else-if="loadingGSCInfo">
        正在加载信息...
    </span>
    <span v-else>
        <span>开始时间：{{ gscInfo.start_time ? toISODateTimeString(gscInfo.start_time) : '未设置' }}</span>
        &nbsp;
        <span>设置开始时间：</span>
        <ElDatePicker v-model="newStartTime" type="datetime" @change="setStartTime" />
        <br>
        <span>结束时间：{{ gscInfo.end_time ? toISODateTimeString(gscInfo.end_time) : '未设置' }}</span>
        &nbsp;
        <span>设置结束时间：</span>
        <ElDatePicker v-model="newEndTime" type="datetime" @change="setEndTime" />
        <br>
        <span>标识：{{ gscInfo.token || '未设置' }}</span>
        &nbsp;
        <span>设置标识：</span>
        <ElInput v-model="newToken" style="width: 300px;" />
        <BaseButton @click="setToken(newToken)">
            修改！
        </BaseButton>
        <br>
        <span>想设置空标识需打开此开关</span><ElSwitch v-model="allowEmptyToken" />
        <br>
        <br>
        <ElDescriptions title="结算后台任务" border :column="2">
            <ElDescriptionsItem label="任务 ID">
                {{ taskInfo?.id ?? '无' }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="状态">
                <DjangoTaskResultStatusBadge :status="taskInfo?.status ?? 'NULL'" />
            </ElDescriptionsItem>
            <ElDescriptionsItem label="创建时间">
                {{ formatTaskTime(taskInfo?.enqueued_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="开始时间">
                {{ formatTaskTime(taskInfo?.started_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="结束时间">
                {{ formatTaskTime(taskInfo?.finished_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem label="异常">
                {{ taskInfo?.exception_class_path || '无' }}
            </ElDescriptionsItem>
        </ElDescriptions>
        <BaseButton :loading="loadingTaskInfo" @click="refreshTaskInfo">
            刷新任务
        </BaseButton>
        <BaseButton :loading="creatingFinishTask" @click="createFinishTask">
            计算排行并结束比赛
        </BaseButton>
        <BaseButton v-if="taskInfo?.status === 'FAILED'" @click="console.log(taskInfo.traceback)">
            输出错误
        </BaseButton>
    </span>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { ElDatePicker, ElDescriptions, ElDescriptionsItem, ElInput, ElSwitch } from 'element-plus';
import { ref, watch } from 'vue';

import { httpErrorNotification, successNotification } from '../Notifications';

import BaseButton from '@/components/common/BaseButton.vue';
import DjangoTaskResultStatusBadge from '@/components/widgets/DjangoTaskResultStatusBadge.vue';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { toDate, toISODateTimeString } from '@/utils/datetime';
import type { GSCInfo } from '@/utils/gsc';
import { utc_to_local_format } from '@/utils/system/tools';

const props = defineProps({
    id: { type: Number, default: 0 },
});

const { proxy } = useCurrentInstance();
const gscInfo = ref<GSCInfo>({ id: 0 });
const newStartTime = ref<Date | undefined>(undefined);
const newEndTime = ref<Date | undefined>(undefined);
const newToken = ref<string>('');
const loadingGSCInfo = ref(false);
const notFound = ref(false);
const allowEmptyToken = ref(false);
const taskInfo = ref<GSCTaskInfo | null>(null);
const loadingTaskInfo = ref(false);
const creatingFinishTask = ref(false);

interface GSCInfoResponseData {
    id: number;
    order: number;
    start_time: string | Date | null;
    end_time: string | Date | null;
    state: string;
    token: string | null;
}

interface GSCTaskInfo {
    id: string;
    status: DjangoTaskResultStatus;
    enqueued_at: string;
    started_at: string | null;
    finished_at: string | null;
    return_value: unknown;
    exception_class_path: string;
    traceback: string;
}

interface TaskResponse {
    type: 'success';
    data: {
        task_id: string;
    };
}

async function getGSCInfo(id: number | undefined) {
    if (id === undefined || id < 1) {
        gscInfo.value = { id: 0 };
        taskInfo.value = null;
        return;
    }
    loadingGSCInfo.value = true;
    notFound.value = false;
    try {
        const { data: tournament } = await proxy.$axios.get<GSCInfoResponseData>('/api/tournament/gsc/admin-info', { params: { order: id } });
        gscInfo.value.start_time = toDate(tournament.start_time);
        gscInfo.value.end_time = toDate(tournament.end_time);
        gscInfo.value.token = tournament.token ?? undefined;
        gscInfo.value.id = tournament.id;
        await refreshTaskInfo();
    } catch (error: unknown) {
        if (isAxiosError(error) && error.response?.status === 404) {
            gscInfo.value = { id: 0 };
            taskInfo.value = null;
            notFound.value = true;
        } else {
            httpErrorNotification(error);
        }
    } finally {
        loadingGSCInfo.value = false;
    }
}

async function refreshTaskInfo() {
    if (props.id < 1) return;
    loadingTaskInfo.value = true;
    await proxy.$axios.get<GSCTaskInfo | null>('/api/tournament/gsc/task', { params: { order: props.id } }).then((response) => {
        taskInfo.value = response.data;
    }).catch(httpErrorNotification);
    loadingTaskInfo.value = false;
}

async function createFinishTask() {
    if (props.id < 1) return;
    creatingFinishTask.value = true;
    await proxy.$axios.post<TaskResponse>('/api/tournament/gsc/task/finish', { order: props.id }).then(async (response) => {
        successNotification(response);
        await refreshTaskInfo();
    }).catch(httpErrorNotification);
    creatingFinishTask.value = false;
}

function formatTaskTime(time: string | null | undefined) {
    if (time === null || time === undefined || time === '') return '无';
    return utc_to_local_format(time);
}

function createGSC() {
    proxy.$axios.post<unknown>('/api/tournament/gsc/new', { id: props.id }).then(
        function (response) {
            successNotification(response);
            void getGSCInfo(props.id);
        },
    ).catch(httpErrorNotification);
}

function setStartTime(time: Date | undefined) {
    if (time === undefined) return;
    proxy.$axios.post<unknown>('/api/tournament/set', { id: gscInfo.value.id, start_time: time.toISOString() }).then(
        function (response) {
            gscInfo.value.start_time = time;
            newStartTime.value = undefined;
            successNotification(response);
        },
    ).catch(httpErrorNotification);
}

function setEndTime(time: Date | undefined) {
    if (time === undefined) return;
    proxy.$axios.post<unknown>('/api/tournament/set', { id: gscInfo.value.id, end_time: time.toISOString() }).then(
        function (response) {
            gscInfo.value.end_time = time;
            newEndTime.value = undefined;
            successNotification(response);
        },
    ).catch(httpErrorNotification);
}

function setToken(token: string) {
    if (token.trim() === '' && !allowEmptyToken.value) return;
    proxy.$axios.post<unknown>('/api/tournament/set', { id: gscInfo.value.id, token: token }).then(
        function (response) {
            gscInfo.value.token = token;
            successNotification(response);
        },
    ).catch(httpErrorNotification);
}

watch(() => props.id, (newId) => {
    if (newId > 0) {
        void getGSCInfo(newId);
    }
}, { immediate: true });
</script>
