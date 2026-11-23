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
        <ElDescriptionsItem v-for="status in DjangoTaskResultStatusOptions" :key="status" :label="t(`local.status.${status}`)">
            {{ taskSummary.status[status] ?? 0 }}
        </ElDescriptionsItem>
    </ElDescriptions>
    <div class="layout-row task-toolbar">
        <BaseButton :loading="loading" :disabled="busy" data-cy="load-tasks" @click="refresh">
            {{ t('local.load') }}
        </BaseButton>
        <BaseButton :loading="cleanupLoading" :disabled="busy" data-cy="cleanup-tasks" @click="cleanupExpiredTasks">
            {{ t('local.cleanup') }}
        </BaseButton>
        <BaseButton :loading="deleting" :disabled="busy || selectedTasks.length === 0" data-cy="delete-tasks" @click="deleteSelected">
            {{ t('local.deleteSelected') }}
        </BaseButton>
        <BaseButton :disabled="busy || (!statusFilter && !taskPath && !taskPathInput)" data-cy="clear-filters" @click="clearFilters">
            {{ t('local.clearFilters') }}
        </BaseButton>
        <span class="text-secondary text-small">{{ t('local.failedHelp', { status: t('local.status.FAILED') }) }}</span>
    </div>
    <div v-loading="loading">
        <BaseTable :empty="taskData.length === 0" :empty-text="t('local.empty')" :column-count="16" data-cy="task-table">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-center">
                        <label class="checkbox">
                            <input class="checkbox-input" type="checkbox" :checked="selectedAll" :indeterminate.prop="selectedSome && !selectedAll" :disabled="busy || taskData.length === 0" :aria-label="t('local.selectPage')" data-cy="select-page" @change="togglePageSelection">
                        </label>
                    </th>
                    <th v-for="column in columns" :key="column.key" scope="col" :aria-sort="column.sort ? sortState(sortOrder, sortField === column.sort) : undefined">
                        <div class="task-head">
                            <BaseButton v-if="column.sort" size="small" text :disabled="busy" :data-cy="`sort-${column.sort}`" @click="toggleSort(column.sort)">
                                <span>{{ t(column.label) }}</span>
                                <SortIcon :state="sortState(sortOrder, sortField === column.sort)" />
                            </BaseButton>
                            <span v-else>{{ t(column.label) }}</span>
                            <select v-if="column.key === 'status'" v-model="statusFilter" class="base-select base-select--small" :disabled="busy" :aria-label="t('prop.status')" data-cy="filter-status" @change="resetStartAndRefresh">
                                <option value="">
                                    {{ t('all') }}
                                </option>
                                <option v-for="status in taskStatusFilterOptions" :key="status" :value="status">
                                    {{ taskStatusLabel(status) }}
                                </option>
                            </select>
                            <input v-if="column.key === 'task_path'" v-model="taskPathInput" class="base-select base-select--small" type="text" :disabled="busy" :aria-label="t('local.taskPath')" data-cy="filter-path" @keydown.enter="applyTaskPath">
                        </div>
                    </th>
                </tr>
            </template>
            <tr v-for="task in taskData" :key="task.id">
                <td class="table-col-center">
                    <label class="checkbox">
                        <input class="checkbox-input" type="checkbox" :checked="isSelected(task.id)" :disabled="busy" :aria-label="t('local.selectTask', { id: task.id })" data-cy="select-task" @change="toggleSelection(task)">
                    </label>
                </td>
                <td>{{ task.id }}</td>
                <td>
                    <BaseButton v-if="task.status === 'FAILED'" data-cy="task-traceback" @click="console.log(task.traceback)">
                        {{ taskStatusLabel(task.status) }}
                    </BaseButton>
                    <template v-else>
                        {{ taskStatusLabel(task.status) }}
                    </template>
                </td>
                <td class="table-col-datetime">
                    {{ toISODateTimeString(toDate(task.enqueued_at)!) }}
                </td>
                <td class="table-col-datetime">
                    {{ task.started_at ? toISODateTimeString(toDate(task.started_at)!) : t('local.notAvailable') }}
                </td>
                <td class="table-col-datetime">
                    {{ task.finished_at ? toISODateTimeString(toDate(task.finished_at)!) : t('local.notAvailable') }}
                </td>
                <td>{{ task.args_kwargs }}</td>
                <td>{{ task.priority }}</td>
                <td>{{ task.task_path }}</td>
                <td>{{ task.worker_ids }}</td>
                <td>{{ task.queue_name }}</td>
                <td>{{ task.backend_name }}</td>
                <td class="table-col-datetime">
                    {{ toISODateTimeString(toDate(task.run_after)!) }}
                </td>
                <td>{{ task.return_value }}</td>
                <td>{{ task.exception_class_path }}</td>
                <td>
                    <BaseButton v-if="task.status === 'FAILED'" :disabled="busy || disabledCrawlingTasks.has(task.task_path)" :loading="restartingTaskId === task.id" data-cy="restart-task" @click="restartTask(task)">
                        {{ t('local.restart') }}
                    </BaseButton>
                </td>
            </tr>
        </BaseTable>
    </div>
    <BasePagination v-model:current-start="currentStart" v-model:page-size="pageSize" :total="totalRecords" :page-size-options="[10, 25, 50, 100]" :disabled="busy" data-cy="task-pagination" @change="refresh" />
</template>

<script setup lang="ts">
import '@/styles/layout.css';

import { ElDescriptions, ElDescriptionsItem, vLoading } from 'element-plus';
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BasePagination from '@/components/common/BasePagination.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import SortIcon from '@/components/common/SortIcon.vue';
import { nextSortOrder, sortState } from '@/components/common/sortState';
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
    args_kwargs: { args: unknown[]; kwargs: Record<string, unknown> };
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
    total: number;
    start: number;
    count: number;
    items: TaskDetail[];
}
interface TaskSummary {
    total: number;
    status: EnumMap<DjangoTaskResultStatus, number>;
}
type TaskSortField = 'enqueued_at' | 'started_at' | 'finished_at' | 'priority' | 'run_after';
const columns: { key: string; label: string; sort?: TaskSortField }[] = [
    { key: 'id', label: 'local.id' },
    { key: 'status', label: 'prop.status' },
    { key: 'enqueued_at', label: 'local.enqueuedAt', sort: 'enqueued_at' },
    { key: 'started_at', label: 'local.startedAt', sort: 'started_at' },
    { key: 'finished_at', label: 'local.finishedAt', sort: 'finished_at' },
    { key: 'args_kwargs', label: 'local.arguments' },
    { key: 'priority', label: 'local.priority', sort: 'priority' },
    { key: 'task_path', label: 'local.taskPath' },
    { key: 'worker_ids', label: 'local.workerIds' },
    { key: 'queue_name', label: 'local.queue' },
    { key: 'backend_name', label: 'local.backend' },
    { key: 'run_after', label: 'local.runAfter', sort: 'run_after' },
    { key: 'return_value', label: 'local.returnValue' },
    { key: 'exception_class_path', label: 'local.exceptionClass' },
    { key: 'action', label: 'prop.action' },
];

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
const deleting = ref(false);
const restartingTaskId = ref<string | null>(null);
const busy = computed(() => loading.value || cleanupLoading.value || deleting.value || restartingTaskId.value !== null);
const currentStart = ref(1);
const pageSize = ref(10);
const totalRecords = ref(0);
const sortField = ref<TaskSortField>('enqueued_at');
const sortOrder = ref<number | undefined>(-1);
const statusFilter = ref<DjangoTaskResultStatus | ''>('');
const taskPath = ref('');
const taskPathInput = ref('');
const taskSummary = ref<TaskSummary>({
    total: 0,
    status: createEnumMap(DjangoTaskResultStatusOptions, 0),
});
const selectedAll = computed(() => taskData.value.length > 0 && taskData.value.every((task) => isSelected(task.id)));
const selectedSome = computed(() => taskData.value.some((task) => isSelected(task.id)));

function isSelected(id: string) {
    return selectedTasks.value.some((task) => task.id === id);
}
function toggleSelection(task: TaskDetail) {
    if (busy.value) return;
    selectedTasks.value = isSelected(task.id)
        ? selectedTasks.value.filter((selected) => selected.id !== task.id)
        : [...selectedTasks.value, task];
}
function togglePageSelection() {
    if (busy.value) return;
    const visibleIds = new Set(taskData.value.map((task) => task.id));
    selectedTasks.value = selectedAll.value
        ? selectedTasks.value.filter((task) => !visibleIds.has(task.id))
        : [...selectedTasks.value.filter((task) => !visibleIds.has(task.id)), ...taskData.value];
}
async function refreshSummary() {
    if (summaryLoading.value) return;
    summaryLoading.value = true;
    try {
        const { data } = await proxy.$axios.get<TaskSummary>('/api/common/tasks/summary');
        taskSummary.value = data;
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        summaryLoading.value = false;
    }
}
async function refresh() {
    if (loading.value) return;
    loading.value = true;
    try {
        // A deletion may shrink the result; refetch the corrected start before displaying that range.
        for (;;) {
            const start = currentStart.value;
            const { data } = await proxy.$axios.get<TaskPage>('/api/common/tasks/detail', {
                params: {
                    start,
                    count: pageSize.value,
                    status: statusFilter.value,
                    task_path: taskPath.value,
                    sort: sortField.value,
                    reverse: sortOrder.value !== 1,
                },
            });
            if (start > Math.max(1, data.total)) {
                currentStart.value = Math.max(1, data.total);
                continue;
            }
            taskData.value = data.items;
            totalRecords.value = data.total;
            const refreshed = new Map(data.items.map((task) => [task.id, task]));
            selectedTasks.value = selectedTasks.value.map((task) => refreshed.get(task.id) ?? task);
            break;
        }
    } catch (error) {
        taskData.value = [];
        httpErrorNotification(error);
    } finally {
        loading.value = false;
    }
}
function resetStartAndRefresh() {
    currentStart.value = 1;
    void refresh();
}
function applyTaskPath() {
    taskPath.value = taskPathInput.value;
    resetStartAndRefresh();
}
function clearFilters() {
    statusFilter.value = '';
    taskPath.value = '';
    taskPathInput.value = '';
    resetStartAndRefresh();
}
function toggleSort(field: TaskSortField) {
    if (busy.value) return;
    sortOrder.value = nextSortOrder(sortOrder.value, sortField.value === field, -1);
    sortField.value = field;
    resetStartAndRefresh();
}

onMounted(() => {
    void refreshSummary();
    void refresh();
});
async function cleanupExpiredTasks() {
    if (busy.value) return;
    cleanupLoading.value = true;
    try {
        await proxy.$axios.post<number>('/api/common/tasks/cleanup');
        selectedTasks.value = [];
        await Promise.all([refreshSummary(), refresh()]);
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        cleanupLoading.value = false;
    }
}
async function restartTask(task: TaskDetail) {
    if (busy.value || disabledCrawlingTasks.has(task.task_path)) return;
    restartingTaskId.value = task.id;
    try {
        await proxy.$axios.post<TaskDetail>('/api/common/tasks/restart', { task_id: task.id });
        await Promise.all([refreshSummary(), refresh()]);
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        restartingTaskId.value = null;
    }
}
async function deleteSelected() {
    if (busy.value || selectedTasks.value.length === 0) return;
    deleting.value = true;
    const deletedTaskIds = new Set<string>();
    try {
        for (const task of [...selectedTasks.value]) {
            await proxy.$axios.post('/api/common/tasks/delete', { task_id: task.id });
            deletedTaskIds.add(task.id);
        }
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        selectedTasks.value = selectedTasks.value.filter((task) => !deletedTaskIds.has(task.id));
        await Promise.all([refreshSummary(), refresh()]);
        deleting.value = false;
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
        clearFilters: '清除筛选',
        empty: '没有任务',
        selectPage: '选择当前区间的任务',
        selectTask: '选择任务 {id}',
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
        clearFilters: 'Clear filters',
        empty: 'No tasks',
        selectPage: 'Select tasks in this range',
        selectTask: 'Select task {id}',
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
    es: { local: {
        overview: 'Resumen',
        failedHelp: 'Para tareas fallidas, haz clic en el botón «{status}» para imprimir el error en la consola.',
        load: 'Cargar tareas',
        cleanup: 'Eliminar tareas expiradas',
        deleteSelected: 'Eliminar tareas seleccionadas',
        clearFilters: 'Borrar filtros',
        empty: 'No hay tareas',
        selectPage: 'Seleccionar tareas de este intervalo',
        selectTask: 'Seleccionar tarea {id}',
        id: 'ID de tarea',
        enqueuedAt: 'Encolado en',
        startedAt: 'Inicio',
        finishedAt: 'Finalización',
        arguments: 'Argumentos',
        priority: 'Prioridad',
        taskPath: 'Ruta de tarea',
        workerIds: 'IDs de trabajadores',
        queue: 'Nombre de la cola',
        backend: 'Nombre del backend',
        runAfter: 'Ejecutar después',
        returnValue: 'Valor de retorno',
        exceptionClass: 'Clase de excepción',
        notAvailable: 'No disponible',
        restart: 'Reiniciar',
        status: {
            READY: 'Listo',
            RUNNING: 'En ejecución',
            SUCCESSFUL: 'Éxito',
            FAILED: 'Fallido',
            NULL: 'Sin estado',
        },
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.task-toolbar {
    align-items: center;
    gap: 6px;
    margin: 6px 0;
}
.task-head {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
}
</style>
