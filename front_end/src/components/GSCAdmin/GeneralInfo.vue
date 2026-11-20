<template>
    <span v-if="id === 0">
        {{ t('local.editionRequired') }}
    </span>
    <span v-else-if="notFound">
        {{ t('local.missingEdition') }}
        <BaseButton @click="createGSC">
            {{ t('local.create') }}
        </BaseButton>
    </span>
    <span v-else-if="loadingGSCInfo">
        {{ t('local.loading') }}
    </span>
    <span v-else>
        <span>{{ t('local.startLabel') }}{{ gscInfo.start_time ? toISODateTimeString(gscInfo.start_time) : t('local.notSet') }}</span>
        &nbsp;
        <span>{{ t('local.setStart') }}</span>
        <ElDatePicker v-model="newStartTime" type="datetime" @change="setStartTime" />
        <br>
        <span>{{ t('local.endLabel') }}{{ gscInfo.end_time ? toISODateTimeString(gscInfo.end_time) : t('local.notSet') }}</span>
        &nbsp;
        <span>{{ t('local.setEnd') }}</span>
        <ElDatePicker v-model="newEndTime" type="datetime" @change="setEndTime" />
        <br>
        <span>{{ t('local.tokenLabel') }}{{ gscInfo.token || t('local.notSet') }}</span>
        &nbsp;
        <span>{{ t('local.setToken') }}</span>
        <ElInput v-model="newToken" style="width: 300px;" />
        <BaseButton @click="setToken(newToken)">
            {{ t('local.apply') }}
        </BaseButton>
        <br>
        <label class="switch" data-cy="allow-empty-token">
            <span>{{ t('local.allowEmpty') }}</span>
            <input v-model="allowEmptyToken" class="switch-input" type="checkbox" role="switch">
            <span class="switch-track" aria-hidden="true" />
        </label>
        <br>
        <br>
        <ElDescriptions :title="t('local.finishTask')" border :column="2">
            <ElDescriptionsItem :label="t('local.taskId')">
                {{ taskInfo?.id ?? t('local.none') }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="t('local.status')">
                <DjangoTaskResultStatusBadge :status="taskInfo?.status ?? 'NULL'" />
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="t('local.created')">
                {{ formatTaskTime(taskInfo?.enqueued_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="t('local.start')">
                {{ formatTaskTime(taskInfo?.started_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="t('local.end')">
                {{ formatTaskTime(taskInfo?.finished_at) }}
            </ElDescriptionsItem>
            <ElDescriptionsItem :label="t('local.exception')">
                {{ taskInfo?.exception_class_path || t('local.none') }}
            </ElDescriptionsItem>
        </ElDescriptions>
        <BaseButton :loading="loadingTaskInfo" @click="refreshTaskInfo">
            {{ t('local.refreshTask') }}
        </BaseButton>
        <BaseButton :loading="creatingFinishTask" @click="createFinishTask">
            {{ t('local.finishCompetition') }}
        </BaseButton>
        <BaseButton v-if="taskInfo?.status === 'FAILED'" @click="console.log(taskInfo.traceback)">
            {{ t('local.printError') }}
        </BaseButton>
    </span>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus.css';
import { isAxiosError } from 'axios';
import { ElDatePicker, ElDescriptions, ElDescriptionsItem, ElInput } from 'element-plus';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

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
const i18nMessages = {
    'zh-cn': { local: {
        allowEmpty: '想设置空标识需打开此开关',
        loading: '正在加载信息...',
        finishCompetition: '计算排行并结束比赛',
        editionRequired: '请输入非零届数',
        missingEdition: '未找到该届信息',
        setStart: '设置开始时间：',
        setEnd: '设置结束时间：',
        finishTask: '结算后台任务',
        startLabel: '开始时间：',
        endLabel: '结束时间：',
        setToken: '设置标识：',
        taskId: '任务 ID',
        create: '创建比赛',
        created: '创建时间',
        start: '开始时间',
        end: '结束时间',
        refreshTask: '刷新任务',
        printError: '输出错误',
        notSet: '未设置',
        tokenLabel: '标识：',
        apply: '修改！',
        status: '状态',
        exception: '异常',
        none: '无',
    } },
    en: { local: {
        allowEmpty: 'Enable to allow an empty token',
        loading: 'Loading tournament information…',
        finishCompetition: 'Calculate rankings and finish the tournament',
        editionRequired: 'Enter a nonzero edition number',
        missingEdition: 'This edition was not found',
        setStart: 'Set start time:',
        setEnd: 'Set end time:',
        finishTask: 'Results calculation task',
        startLabel: 'Start time: ',
        endLabel: 'End time: ',
        setToken: 'Set token:',
        taskId: 'Task ID',
        create: 'Create tournament',
        created: 'Created at',
        start: 'Start time',
        end: 'End time',
        refreshTask: 'Refresh task',
        printError: 'Print error',
        notSet: 'Not set',
        tokenLabel: 'Token: ',
        apply: 'Apply',
        status: 'Status',
        exception: 'Exception',
        none: 'None',
    } },
    es: { local: {
        allowEmpty: 'Activa esta opción para permitir un identificador vacío',
        loading: 'Cargando los datos del torneo…',
        finishCompetition: 'Calcular la clasificación y finalizar el torneo',
        editionRequired: 'Introduce un número de edición distinto de cero',
        missingEdition: 'No se encontró esta edición',
        setStart: 'Definir el inicio:',
        setEnd: 'Definir el fin:',
        finishTask: 'Tarea de cálculo de resultados',
        startLabel: 'Inicio: ',
        endLabel: 'Fin: ',
        setToken: 'Definir identificador:',
        taskId: 'ID de tarea',
        create: 'Crear torneo',
        created: 'Fecha de creación',
        start: 'Inicio',
        end: 'Fin',
        refreshTask: 'Actualizar tarea',
        printError: 'Mostrar el error',
        notSet: 'Sin definir',
        tokenLabel: 'Identificador: ',
        apply: 'Aplicar',
        status: 'Estado',
        exception: 'Excepción',
        none: 'Ninguno',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

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
    if (time === null || time === undefined || time === '') return t('local.none');
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
