<template>
    <ElDescriptions v-loading="summaryLoading" :title="t('local.overview')" border :column="5">
        <template #extra>
            <BaseButton :loading="summaryLoading" @click="refreshSummary">
                {{ t('action.refresh') }}
            </BaseButton>
        </template>
        <ElDescriptionsItem :label="t('score.total')">
            {{ taskSummary.total }}
        </ElDescriptionsItem>
        <ElDescriptionsItem
            v-for="status in DjangoTaskResultStatusOptions"
            :key="status"
            :label="t(`local.status.${status}`)"
        >
            {{ taskSummary.status[status] ?? 0 }}
        </ElDescriptionsItem>
    </ElDescriptions>
    <PrToolbar>
        {{ t('local.failedHelp', { status: t('local.status.FAILED') }) }}
        <template #start>
            <BaseButton :loading="loading" @click="refresh">
                {{ t('local.load') }}
            </BaseButton>
            <BaseButton :loading="cleanupLoading" @click="cleanupExpiredTasks">
                {{ t('local.cleanup') }}
            </BaseButton>
            <BaseButton :disabled="selectedTasks.length === 0" @click="deleteSelected">
                {{ t('local.deleteSelected') }}
            </BaseButton>
        </template>
    </PrToolbar>
    <PrDataTable
        v-model:first="first"
        v-model:rows="rows"
        v-model:filters="filters"
        v-model:selection="selectedTasks"
        v-model:sort-field="sortField"
        v-model:sort-order="sortOrder"
        v-loading="loading"
        :value="taskData"
        lazy
        :total-records="totalRecords"
        filter-display="menu"
        paginator
        :rows-per-page-options="[10, 25, 50, 100]"
        paginator-template="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown JumpToPageInput CurrentPageReport"
        @page="refresh"
        @sort="refresh"
        @filter="refresh"
    >
        <PrColumn selection-mode="multiple" />
        <PrColumn field="id" :header="t('local.id')" />
        <PrColumn field="status" :header="t('prop.status')" :show-filter-match-modes="false" :show-filter-operator="false">
            <template #body="{ data }">
                <BaseButton v-if="data.status === 'FAILED'" @click="console.log(data.traceback)">
                    {{ t(`local.status.${data.status}`) }}
                </BaseButton>
                <template v-else>
                    {{ t(`local.status.${data.status}`) }}
                </template>
            </template>
            <template #filter="{ filterModel, filterCallback }">
                <PrSelect v-model="filterModel.value" :options="taskStatusFilterOptions" :option-label="taskStatusLabel" @change="filterCallback()" />
            </template>
        </PrColumn>
        <PrColumn field="enqueued_at" :header="t('local.enqueuedAt')" sortable>
            <template #body="{ data }">
                {{ toISODateTimeString(toDate(data.enqueued_at)!) }}
            </template>
        </PrColumn>
        <PrColumn field="started_at" :header="t('local.startedAt')" sortable>
            <template #body="{ data }">
                {{ data.started_at ? toISODateTimeString(toDate(data.started_at)!) : t('local.notAvailable') }}
            </template>
        </PrColumn>
        <PrColumn field="finished_at" :header="t('local.finishedAt')" sortable>
            <template #body="{ data }">
                {{ data.finished_at ? toISODateTimeString(toDate(data.finished_at)!) : t('local.notAvailable') }}
            </template>
        </PrColumn>
        <PrColumn field="args_kwargs" :header="t('local.arguments')" />
        <PrColumn field="priority" :header="t('local.priority')" sortable />
        <PrColumn field="task_path" :header="t('local.taskPath')" :show-filter-match-modes="false" :show-filter-operator="false">
            <template #filter="{ filterModel, filterCallback }">
                <PrInputText v-model="filterModel.value" :aria-label="t('local.taskPath')" @keydown.enter="filterCallback()" />
            </template>
        </PrColumn>
        <PrColumn field="worker_ids" :header="t('local.workerIds')" />
        <PrColumn field="queue_name" :header="t('local.queue')" />
        <PrColumn field="backend_name" :header="t('local.backend')" />
        <PrColumn field="run_after" :header="t('local.runAfter')" sortable>
            <template #body="{ data }">
                {{ toISODateTimeString(toDate(data.run_after)!) }}
            </template>
        </PrColumn>
        <PrColumn field="return_value" :header="t('local.returnValue')" />
        <PrColumn field="exception_class_path" :header="t('local.exceptionClass')" />
        <PrColumn :header="t('prop.action')">
            <template #body="{ data }">
                <BaseButton
                    v-if="data.status === 'FAILED'"
                    :disabled="disabledCrawlingTasks.has(data.task_path)"
                    :loading="restartingTaskId === data.id"
                    @click="restartTask(data)"
                >
                    {{ t('local.restart') }}
                </BaseButton>
            </template>
        </PrColumn>
    </PrDataTable>
</template>

<script setup lang="ts">
import { FilterMatchMode } from '@primevue/core/api';
import { ElDescriptions, ElDescriptionsItem, vLoading } from 'element-plus';
import PrColumn from 'primevue/column';
import PrDataTable from 'primevue/datatable';
import PrInputText from 'primevue/inputtext';
import PrSelect from 'primevue/select';
import PrToolbar from 'primevue/toolbar';
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { createEnumMap } from '@/utils';
import type { EnumMap } from '@/utils';
import type { DjangoTaskResultStatus } from '@/utils/common/structInterface';
import { DjangoTaskResultStatusOptions } from '@/utils/common/structInterface';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { toDate, toISODateTimeString } from '@/utils/datetime';

interface TaskDetail {
    id: string;
    status: DjangoTaskResultStatus;
    enqueued_at: string;
    started_at: string | null;
    finished_at: string | null;
    args_kwargs: {
        args: unknown[];
        kwargs: Record<string, unknown>;
    };
    priority: number;
    task_path: string;
    worker_ids: string[];
    queue_name: string;
    backend_name: string;
    run_after: string;
    return_value: unknown;
    exception_class_path: string;
    traceback: string;
}

interface TaskPage {
    count: number;
    page: number;
    page_size: number;
    items: TaskDetail[];
}

interface TaskSummary {
    total: number;
    status: EnumMap<DjangoTaskResultStatus, number>;
}

const { proxy } = useCurrentInstance();

const disabledCrawlingTasks = new Set([
    'accountlink.tasks.task_saolei_profile',
    'accountlink.tasks.task_saolei_video_import',
    'accountlink.tasks.task_saolei_video_import_bulk',
]);

const taskStatusFilterOptions = DjangoTaskResultStatusOptions.filter((status) => status !== 'NULL');

const taskData = ref<TaskDetail[]>([]);
const selectedTasks = ref<TaskDetail[]>([]);
const loading = ref(false);
const summaryLoading = ref(false);
const cleanupLoading = ref(false);
const restartingTaskId = ref<string | null>(null);
const first = ref(0);
const rows = ref(10);
const totalRecords = ref(0);
const sortField = ref('enqueued_at');
const sortOrder = ref<number | undefined>(-1);
const taskSummary = ref<TaskSummary>({
    total: 0,
    status: createEnumMap(DjangoTaskResultStatusOptions, 0),
});

const filters = ref({
    status: { value: null as DjangoTaskResultStatus | null, matchMode: FilterMatchMode.EQUALS },
    task_path: { value: null as string | null, matchMode: FilterMatchMode.CONTAINS },
});

async function refreshSummary() {
    summaryLoading.value = true;
    await proxy.$axios.get<TaskSummary>('/api/common/tasks/summary').then((response) => {
        taskSummary.value = response.data;
    }).catch(httpErrorNotification);
    summaryLoading.value = false;
}

async function refresh() {
    loading.value = true;
    await proxy.$axios.get<TaskPage>('/api/common/tasks/detail', {
        params: {
            page: Math.floor(first.value / rows.value) + 1,
            page_size: rows.value,
            status: filters.value.status.value ?? '',
            task_path: filters.value.task_path.value ?? '',
            sort: sortField.value,
            reverse: sortOrder.value !== 1,
        },
    }).then((response) => {
        taskData.value = response.data.items;
        totalRecords.value = response.data.count;
    }).catch(httpErrorNotification);
    loading.value = false;
}

onMounted(() => {
    void refreshSummary();
    void refresh();
});

async function cleanupExpiredTasks() {
    cleanupLoading.value = true;
    await proxy.$axios.post<number>('/api/common/tasks/cleanup').then(async () => {
        await Promise.all([refreshSummary(), refresh()]);
    }).catch(httpErrorNotification);
    cleanupLoading.value = false;
}

async function restartTask(task: TaskDetail) {
    restartingTaskId.value = task.id;
    try {
        await proxy.$axios.post<TaskDetail>('/api/common/tasks/restart', {
            task_id: task.id,
        });
        await Promise.all([refreshSummary(), refresh()]);
    } catch (error) {
        httpErrorNotification(error);
    }
    restartingTaskId.value = null;
}

async function deleteSelected() {
    if (selectedTasks.value.length === 0) return;
    const deletedTaskIds = new Set<string>();
    try {
        for (const task of selectedTasks.value) {
            await proxy.$axios.post('/api/common/tasks/delete', {
                task_id: task.id,
            });
            deletedTaskIds.add(task.id);
        }
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        selectedTasks.value = selectedTasks.value.filter((task) => !deletedTaskIds.has(task.id));
        await Promise.all([refreshSummary(), refresh()]);
    }
}

function taskStatusLabel(status: string) {
    return t(`local.status.${status}`);
}

const i18nMessages = {
    'zh-cn': { local: {
        overview: '概览',
        failedHelp: '对于失败的任务，点击“{status}”按钮可以在控制台输出报错。',
        load: '加载任务',
        cleanup: '删除过期任务',
        deleteSelected: '删除选中任务',
        id: '任务 ID',
        enqueuedAt: '入队时间',
        startedAt: '开始时间',
        finishedAt: '完成时间',
        arguments: '参数',
        priority: '优先级',
        taskPath: '任务路径',
        workerIds: '工作进程 ID',
        queue: '队列名称',
        backend: '后端名称',
        runAfter: '最早执行时间',
        returnValue: '返回值',
        exceptionClass: '异常类型路径',
        notAvailable: '无',
        restart: '重启',
        status: {
            READY: '就绪',
            RUNNING: '运行中',
            SUCCESSFUL: '成功',
            FAILED: '失败',
            NULL: '无状态',
        },
    } },
    en: { local: {
        overview: 'Overview',
        failedHelp: 'For failed tasks, click the “{status}” button to print the error to the console.',
        load: 'Load tasks',
        cleanup: 'Delete expired tasks',
        deleteSelected: 'Delete selected tasks',
        id: 'Task ID',
        enqueuedAt: 'Enqueued at',
        startedAt: 'Started at',
        finishedAt: 'Finished at',
        arguments: 'Arguments',
        priority: 'Priority',
        taskPath: 'Task path',
        workerIds: 'Worker IDs',
        queue: 'Queue name',
        backend: 'Backend name',
        runAfter: 'Run after',
        returnValue: 'Return value',
        exceptionClass: 'Exception class path',
        notAvailable: 'N/A',
        restart: 'Restart',
        status: {
            READY: 'Ready',
            RUNNING: 'Running',
            SUCCESSFUL: 'Successful',
            FAILED: 'Failed',
            NULL: 'No status',
        },
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
