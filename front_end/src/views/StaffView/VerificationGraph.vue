<template>
    <div>
        <div v-if="!store.user.is_superuser" class="text-danger">
            {{ t('local.superuserOnly') }}
        </div>
        <div>
            {{ t('local.maintenance') }}{{ t('punct.colon') }}{{ maintenanceSummary }}
        </div>
        <div>
            <label for="verification-duration">{{ t('local.duration') }}</label>
            <input id="verification-duration" v-model="duration" type="number" min="1" max="3600" class="verification-graph__input">
            <BaseButton :loading="busy" :disabled="!store.user.is_superuser || maintenance?.active === true" data-cy="verification-maintenance-start" @click="startSession">
                {{ t('local.startMaintenance') }}
            </BaseButton>
            <BaseButton :loading="busy" :disabled="!store.user.is_superuser || maintenance?.owned_by_requester !== true" data-cy="verification-maintenance-end" @click="endSession">
                {{ t('local.endMaintenance') }}
            </BaseButton>
        </div>
        <div>
            <BaseButton :loading="busy" :disabled="!store.user.is_superuser" data-cy="verification-graph-load" @click="loadGraph">
                {{ t('local.loadGraph') }}
            </BaseButton>
        </div>
        <pre v-if="graph" class="verification-graph__snapshot" data-cy="verification-graph-snapshot">{{ JSON.stringify(graph, null, 2) }}</pre>
        <div>
            {{ t('local.batch') }}
            <textarea v-model="batchText" class="verification-graph__editor" rows="12" data-cy="verification-graph-batch" />
        </div>
        <div>
            <BaseButton :loading="busy" :disabled="!store.user.is_superuser || maintenance?.owned_by_requester !== true" data-cy="verification-graph-submit" @click="submitBatch">
                {{ t('local.submitBatch') }}
            </BaseButton>
            <span v-if="resultText" role="status" data-cy="verification-graph-result">{{ resultText }}</span>
        </div>
    </div>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { actionSuccessNotification, baseErrorNotification, generalErrorNotification, httpErrorNotification } from '@/components/Notifications';
import {
    endVerificationMaintenance, fetchVerificationGraph, startVerificationMaintenance, submitVerificationGraphUpdate,
} from '@/services/playerVerificationService';
import type { GraphEdgeCommand, GraphNodeCommand, GraphUpdateCommand, MaintenanceState, VerificationGraph } from '@/services/playerVerificationService';
import { store } from '@/store';

const maintenance = ref<MaintenanceState | null>(null);
const graph = ref<VerificationGraph | null>(null);
const duration = ref<number | string>(300);
const batchText = ref('{"add_edges": [], "remove_edges": [], "set_verified": []}');
const busy = ref(false);
const resultText = ref('');

const maintenanceSummary = computed(() => {
    const state = maintenance.value;
    if (state === null) return t('local.unknown');
    if (!state.active) return t('local.inactive');
    return `${state.owner_id} / ${state.expires_at ?? ''} / ${state.owned_by_requester ? t('local.owned') : t('local.notOwned')}`;
});

function showError(error: unknown): void {
    if (isAxiosError<{ object?: string; category?: string }>(error) && error.response?.data?.object === 'verification') {
        generalErrorNotification('verification', error.response.data.category ?? 'not_found');
    } else {
        httpErrorNotification(error);
    }
}

async function withBusy(action: () => Promise<void>): Promise<void> {
    busy.value = true;
    resultText.value = '';
    try {
        await action();
    } catch (error) {
        showError(error);
    } finally {
        busy.value = false;
    }
}

async function loadGraph(): Promise<void> {
    await withBusy(async () => {
        graph.value = await fetchVerificationGraph();
        maintenance.value = graph.value.maintenance;
    });
}

function validDuration(): number | null {
    const value = Number(duration.value);
    if (!Number.isInteger(value) || value < 1 || value > 3600) {
        baseErrorNotification(t('local.jsonError'), t('local.invalidDuration'));
        return null;
    }
    return value;
}

function startSession(): void {
    const seconds = validDuration();
    if (seconds === null) return;
    void withBusy(async () => {
        maintenance.value = await startVerificationMaintenance(seconds);
        resultText.value = t('local.maintenanceStarted');
        actionSuccessNotification();
    });
}

function endSession(): void {
    void withBusy(async () => {
        await endVerificationMaintenance();
        await loadGraph();
        resultText.value = t('local.maintenanceEnded');
    });
}

function isEdgeCommand(value: unknown): value is GraphEdgeCommand {
    if (typeof value !== 'object' || value === null) return false;
    const item = value as Record<string, unknown>;
    return Number.isInteger(item.from_user_id) && Number.isInteger(item.to_user_id);
}

function isNodeCommand(value: unknown): value is GraphNodeCommand {
    if (typeof value !== 'object' || value === null) return false;
    const item = value as Record<string, unknown>;
    return Number.isInteger(item.user_id) && typeof item.verified === 'boolean';
}

function asCommands<T>(value: unknown, guard: (item: unknown) => item is T): T[] | null {
    if (!Array.isArray(value)) return null;
    const items: unknown[] = value;
    const result: T[] = [];
    for (const item of items) {
        if (!guard(item)) return null;
        result.push(item);
    }
    return result;
}

function parseBatch(): GraphUpdateCommand | null {
    let payload: unknown;
    try {
        payload = JSON.parse(batchText.value) as unknown;
    } catch (error) {
        baseErrorNotification(t('local.jsonError'), String(error));
        return null;
    }
    if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
        baseErrorNotification(t('local.jsonError'), t('local.batchFormat'));
        return null;
    }
    const data = payload as Record<string, unknown>;
    const addEdges = asCommands(data.add_edges ?? [], isEdgeCommand);
    const removeEdges = asCommands(data.remove_edges ?? [], isEdgeCommand);
    const nodes = asCommands(data.set_verified ?? [], isNodeCommand);
    if (addEdges === null || removeEdges === null || nodes === null) {
        baseErrorNotification(t('local.jsonError'), t('local.batchFormat'));
        return null;
    }
    return { add_edges: addEdges, remove_edges: removeEdges, set_verified: nodes };
}

function submitBatch(): void {
    const command = parseBatch();
    if (command === null) return;
    void withBusy(async () => {
        const result = await submitVerificationGraphUpdate(command);
        actionSuccessNotification();
        await loadGraph();
        resultText.value = JSON.stringify(result);
    });
}

const i18nMessages = {
    'zh-cn': { local: {
        superuserOnly: '仅站长可使用认证图维护。',
        maintenance: '维护会话',
        unknown: '未读取',
        inactive: '未开启',
        owned: '本人持有',
        notOwned: '其他站长持有',
        duration: '会话秒数（1–3600）',
        invalidDuration: '会话秒数必须是 1 到 3600 之间的整数',
        startMaintenance: '开启维护会话',
        endMaintenance: '结束维护会话',
        maintenanceStarted: '维护会话已开启，全站暂停普通认证与管理员设置认证。',
        maintenanceEnded: '维护会话已结束。',
        loadGraph: '读取当前认证图',
        batch: '完整批次（JSON）',
        jsonError: 'JSON 错误',
        batchFormat: '批次必须包含 add_edges、remove_edges、set_verified 三个数组，元素字段为整数 ID 与布尔值。',
        submitBatch: '提交完整批次',
    } },
    en: { local: {
        superuserOnly: 'Only a superuser can maintain the verification graph.',
        maintenance: 'Maintenance session',
        unknown: 'Not loaded',
        inactive: 'Inactive',
        owned: 'Owned by you',
        notOwned: 'Owned by another superuser',
        duration: 'Session seconds (1–3600)',
        invalidDuration: 'Session seconds must be an integer between 1 and 3600',
        startMaintenance: 'Start maintenance',
        endMaintenance: 'End maintenance',
        maintenanceStarted: 'Maintenance started. Ordinary verification and admin-set verification are paused.',
        maintenanceEnded: 'Maintenance session ended.',
        loadGraph: 'Read current graph',
        batch: 'Complete batch (JSON)',
        jsonError: 'JSON error',
        batchFormat: 'The batch needs add_edges, remove_edges and set_verified arrays with integer IDs and boolean values.',
        submitBatch: 'Submit complete batch',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.verification-graph__input {
    width: 6rem;
    margin: 0 0.5rem;
}

.verification-graph__editor,
.verification-graph__snapshot {
    display: block;
    width: 100%;
    max-height: 24rem;
    overflow: auto;
    margin: 0.5rem 0;
    border: 1px solid var(--el-border-color);
    border-radius: 0;
    background: var(--el-bg-color);
    color: var(--el-text-color-primary);
}
</style>
