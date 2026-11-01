<template>
    <p v-if="!isStaff">
        {{ t('local.staffOnly') }}
    </p>
    <div v-else class="staff-medals">
        <form class="player-form" @submit.prevent="loadPlayer()">
            <label>
                {{ t('common.prop.userId') }}
                <ElInputNumber v-model="userId" :min="1" :precision="0" :controls="false" :disabled="saving" :aria-label="t('common.prop.userId')" />
            </label>
            <BaseButton native-type="submit" :disabled="!validUser || saving" :loading="loading">
                {{ t('local.reload') }}
            </BaseButton>
        </form>
        <p v-if="catalogError" role="alert">
            {{ t('local.catalogFailed') }}
            <BaseButton @click="loadCatalog">
                {{ t('local.reload') }}
            </BaseButton>
        </p>
        <p v-if="error" role="alert">
            {{ error }}
        </p>
        <output v-if="notice" aria-live="polite">{{ notice }}</output>
        <template v-if="player">
            <p class="player-label">
                {{ player.username }} (#{{ player.user_id }})
            </p>
            <form class="override-form" @submit.prevent="save">
                <label>
                    {{ t('local.medal') }}
                    <ElSelect v-model="code" filterable :disabled="saving" :aria-label="t('local.medal')">
                        <ElOption v-for="option in medalOptions" :key="option.code" :value="option.code" :label="option.label" />
                    </ElSelect>
                </label>
                <label>
                    {{ t('local.scope') }}
                    <ElInput v-model="scope" :disabled="saving || (mode !== 'auto' && !!definition && !staffMedalAllowsScope(definition))" :aria-label="t('local.scope')" />
                </label>
                <p class="help">
                    {{ t('local.scopeHelp') }}
                </p>
                <label>
                    {{ t('local.action') }}
                    <ElSelect v-model="mode" :disabled="saving" :aria-label="t('local.action')">
                        <ElOption value="grant" :label="t('local.grant')" :disabled="!definition?.active" />
                        <ElOption value="revoke" :label="t('local.revoke')" :disabled="!definition" />
                        <ElOption value="auto" :label="t('local.auto')" :disabled="!currentOverride" />
                    </ElSelect>
                </label>
                <p class="help">
                    {{ t(`local.${mode}Help`) }}
                </p>
                <template v-if="mode === 'grant'">
                    <label>
                        {{ t('local.stage') }}
                        <ElSelect v-model="stage" :disabled="saving" :aria-label="t('local.stage')">
                            <ElOption v-for="threshold in stages" :key="threshold" :value="threshold" :label="stageLabel(code, threshold)" />
                        </ElSelect>
                    </label>
                    <label>
                        {{ t('local.grantedOn') }}
                        <input v-model="grantedOn" type="date" :disabled="saving" required>
                    </label>
                </template>
                <label>
                    {{ t('local.reason') }}
                    <ElInput v-model="reason" type="textarea" :disabled="saving" :aria-label="t('local.reason')" />
                </label>
                <BaseButton native-type="submit" :disabled="!canSave" :loading="saving">
                    {{ t('local.apply') }}
                </BaseButton>
            </form>

            <h3>{{ t('local.overrides') }}</h3>
            <BaseTable :empty="!player.overrides.length" :empty-text="t('local.none')" :column-count="6" data-cy="overrides">
                <template #head>
                    <tr><th>{{ t('local.medal') }}</th><th>{{ t('local.scope') }}</th><th>{{ t('local.action') }}</th><th>{{ t('local.stage') }}</th><th>{{ t('local.reason') }}</th><th>{{ t('local.auto') }}</th></tr>
                </template>
                <tr v-for="item in player.overrides" :key="item.id">
                    <td>{{ definitionLabel(item.definition_code) }}</td><td>{{ item.scope_key || '—' }}</td><td>{{ t(`local.${item.mode}`) }}</td><td>{{ stageLabel(item.definition_code, item.stage) }}</td><td>{{ item.reason }}</td>
                    <td>
                        <BaseButton :disabled="saving" @click="prepareAuto(item)">
                            {{ t('local.auto') }}
                        </BaseButton>
                    </td>
                </tr>
            </BaseTable>
            <h3>{{ t('local.grants') }}</h3>
            <BaseTable :empty="!player.grants.length" :empty-text="t('local.none')" :column-count="6" data-cy="grants">
                <template #head>
                    <tr><th>{{ t('local.medal') }}</th><th>{{ t('local.scope') }}</th><th>{{ t('local.stage') }}</th><th>{{ t('local.grantedOn') }}</th><th>{{ t('local.revokedAt') }}</th><th>{{ t('local.reason') }}</th></tr>
                </template>
                <tr v-for="item in player.grants" :key="item.id">
                    <td>{{ definitionLabel(item.definition_code) }}</td><td>{{ item.scope_key || '—' }}</td><td>{{ stageLabel(item.definition_code, item.stage) }}</td><td>{{ item.granted_at }}</td><td>{{ item.revoked_at || '—' }}</td><td>{{ item.revoke_reason }}</td>
                </tr>
            </BaseTable>
            <h3>{{ t('local.history') }}</h3>
            <BaseTable :empty="!player.history.length" :empty-text="t('local.none')" :column-count="7" data-cy="history">
                <template #head>
                    <tr><th>{{ t('local.medal') }}</th><th>{{ t('local.scope') }}</th><th>{{ t('local.action') }}</th><th>{{ t('local.stage') }}</th><th>{{ t('local.reason') }}</th><th>{{ t('local.actor') }}</th><th>{{ t('local.date') }}</th></tr>
                </template>
                <tr v-for="item in player.history" :key="item.id">
                    <td>{{ definitionLabel(item.definition_code) }}</td><td>{{ item.scope_key || '—' }}</td><td>{{ t(`local.${item.action}`) }}</td><td>{{ stageLabel(item.definition_code, item.stage) }}</td><td>{{ item.reason }}</td><td>{{ item.actor_id ?? '—' }}</td><td>{{ item.created_at }}</td>
                </tr>
            </BaseTable>
        </template>
    </div>
</template>

<script setup lang="ts">
import { ElInput, ElInputNumber, ElOption, ElSelect } from 'element-plus';
import { computed, onActivated, onDeactivated, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { medalSeriesLabel, medalStageLabel, refreshPlayerMedals } from '@/services/medalService';
import type { MedalOverrideInput, MedalOverrideMode, StaffMedalDefinition, StaffMedalOverride, StaffPlayerMedals } from '@/services/staffMedalService';
import { fetchStaffMedalCatalog, fetchStaffPlayerMedals, setMedalOverride, staffMedalAllowsScope, staffMedalStages, validMedalOverride } from '@/services/staffMedalService';
import { store } from '@/store';

const userId = ref<number>();
const catalog = ref<StaffMedalDefinition[]>([]);
const catalogLoaded = ref(false);
const catalogError = ref(false);
const player = ref<StaffPlayerMedals | null>(null);
const code = ref('');
const scope = ref('');
const mode = ref<MedalOverrideMode>('grant');
const stage = ref<number>();
const grantedOn = ref('');
const reason = ref('');
const error = ref('');
const notice = ref('');
const loading = ref(false);
const saving = ref(false);
const viewing = ref(true);
const isStaff = computed(() => store.user.is_staff);
const validUser = computed(() => userId.value !== undefined && Number.isSafeInteger(userId.value) && userId.value > 0);
const definition = computed(() => catalog.value.find((item) => item.code === code.value));
const stages = computed(() => (definition.value ? staffMedalStages(definition.value) : []));
const currentOverride = computed(() => player.value?.overrides.find((item) => item.definition_code === code.value && item.scope_key === scope.value.trim()));
const medalOptions = computed(() => [...new Set([
    ...catalog.value.map((item) => item.code),
    ...player.value?.overrides.map((item) => item.definition_code) ?? [],
    ...player.value?.grants.map((item) => item.definition_code) ?? [],
])].map((itemCode) => ({ code: itemCode, label: definitionLabel(itemCode) })));
const input = computed<MedalOverrideInput>(() => ({
    user_id: userId.value ?? 0,
    code: code.value,
    scope_key: scope.value.trim(),
    mode: mode.value,
    reason: reason.value.trim(),
    ...mode.value === 'grant' ? { stage: stage.value, granted_on: grantedOn.value } : {},
}));
const canSave = computed(() => isStaff.value && viewing.value && !loading.value && !saving.value && player.value?.user_id === userId.value && validMedalOverride(input.value, definition.value, !!currentOverride.value));
let playerRequest = 0;
let catalogRequest = 0;

function definitionLabel(itemCode: string) {
    const item = catalog.value.find((entry) => entry.code === itemCode);
    return item ? `${medalSeriesLabel(item.series, locale.value)} / ${item.code}${item.active ? '' : ` (${t('local.inactive')})`}` : `${itemCode} (${t('local.deleted')})`;
}

function stageLabel(itemCode: string, value: number | null) {
    if (value === null) return '—';
    const item = catalog.value.find((entry) => entry.code === itemCode);
    const label = item ? medalStageLabel(item.series, value) : '';
    return label ? `${label} (${value})` : String(value);
}

async function loadCatalog() {
    if (!isStaff.value || !viewing.value) return;
    const request = ++catalogRequest;
    catalogError.value = false;
    try {
        const data = await fetchStaffMedalCatalog();
        if (request !== catalogRequest || !isStaff.value || !viewing.value) return;
        catalog.value = data;
        catalogLoaded.value = true;
    } catch {
        if (request === catalogRequest && isStaff.value && viewing.value) catalogError.value = true;
    }
}

async function loadPlayer(preserveNotice = false) {
    if (!isStaff.value || !viewing.value || !validUser.value || userId.value === undefined) return;
    const id = userId.value;
    const request = ++playerRequest;
    loading.value = true;
    error.value = '';
    if (!preserveNotice) notice.value = '';
    try {
        const data = await fetchStaffPlayerMedals(id);
        if (request !== playerRequest || userId.value !== id || !isStaff.value || !viewing.value) return;
        player.value = data;
        if (!preserveNotice) refreshPlayerMedals(id);
    } catch {
        if (request === playerRequest && isStaff.value && viewing.value) error.value = t('local.loadFailed');
    } finally {
        if (request === playerRequest) loading.value = false;
    }
}

function prepareAuto(item: StaffMedalOverride) {
    code.value = item.definition_code;
    scope.value = item.scope_key;
    mode.value = 'auto';
    reason.value = '';
}

async function save() {
    if (!canSave.value) return;
    const submitted = { ...input.value };
    const request = playerRequest;
    saving.value = true;
    error.value = '';
    notice.value = '';
    try {
        const result = await setMedalOverride(submitted);
        if (request !== playerRequest || !isStaff.value || !viewing.value || userId.value !== submitted.user_id) return;
        notice.value = t(result.enqueued ? 'local.queued' : 'local.saved');
        reason.value = '';
        await loadPlayer(true);
    } catch {
        if (request === playerRequest && isStaff.value && viewing.value && userId.value === submitted.user_id) error.value = t('local.saveFailed');
    } finally {
        saving.value = false;
    }
}

watch(userId, () => {
    playerRequest += 1;
    player.value = null;
    loading.value = false;
    error.value = '';
    notice.value = '';
    code.value = '';
    scope.value = '';
    mode.value = 'grant';
    reason.value = '';
    grantedOn.value = '';
}, { flush: 'sync' });
watch(code, () => {
    stage.value = undefined;
}, { flush: 'sync' });
watch([definition, mode], () => {
    if (mode.value !== 'auto' && definition.value && !staffMedalAllowsScope(definition.value)) scope.value = '';
});

function deactivate() {
    viewing.value = false;
    playerRequest += 1;
    catalogRequest += 1;
    loading.value = false;
}
onActivated(() => {
    viewing.value = true;
});
onDeactivated(deactivate);
onUnmounted(deactivate);

const i18nMessages = {
    'zh-cn': { local: {
        staffOnly: '仅管理员可使用勋章管理。',
        reload: '重新加载',
        medal: '勋章',
        scope: '届次 / 范围键（可选）',
        scopeHelp: '普通勋章留空；比赛勋章按届次区分。人工决定仅作用于该勋章和范围。',
        action: '操作',
        grant: '强制发放',
        revoke: '撤销 / 禁止发放',
        auto: '恢复自动',
        grantHelp: '锁定指定档位，直到恢复自动。不会改写真实进度，也不会连带发放衍生勋章。',
        revokeHelp: '撤销当前授予，并禁止自动发放；尚未获得时也可提前禁发，直到恢复自动。',
        autoHelp: '解除该范围的人工决定，等待后台任务按真实进度重算。',
        stage: '档位',
        grantedOn: '授予日期',
        reason: '原因（必填）',
        apply: '应用操作',
        overrides: '当前人工决定',
        grants: '授予记录',
        history: '最近 50 条人工操作',
        revokedAt: '撤销时间',
        actor: '操作员 ID',
        date: '操作时间',
        none: '无记录',
        inactive: '已停用',
        deleted: '定义已删除',
        saved: '人工决定已保存。',
        queued: '已恢复自动，等待后台任务重算。请稍后点击重新加载查看结果。',
        catalogFailed: '勋章目录加载失败。',
        loadFailed: '玩家勋章加载失败，请重新加载。',
        saveFailed: '操作未保存，请检查参数和权限后重试。',
    } },
    en: { local: {
        staffOnly: 'Medal management is available to staff only.',
        reload: 'Reload',
        medal: 'Medal',
        scope: 'Edition / scope key (optional)',
        scopeHelp: 'Leave blank for ordinary medals; distinguish tournament medals by edition. Decisions apply only to this medal and scope.',
        action: 'Action',
        grant: 'Force grant',
        revoke: 'Revoke / block grants',
        auto: 'Restore automatic',
        grantHelp: 'Locks the selected stage until automatic awards are restored. Actual progress and derived medals are unchanged.',
        revokeHelp: 'Revokes the current award and blocks automatic grants, including before a medal is earned, until automatic awards are restored.',
        autoHelp: 'Removes the manual decision for this scope. A background task will recalculate from actual progress.',
        stage: 'Stage',
        grantedOn: 'Award date',
        reason: 'Reason (required)',
        apply: 'Apply action',
        overrides: 'Current manual decisions',
        grants: 'Award records',
        history: 'Latest 50 manual actions',
        revokedAt: 'Revoked at',
        actor: 'Operator ID',
        date: 'Action time',
        none: 'No records',
        inactive: 'Inactive',
        deleted: 'Definition deleted',
        saved: 'Manual decision saved.',
        queued: 'Automatic awards restored; waiting for the background task. Reload shortly to see the result.',
        catalogFailed: 'The medal catalog could not be loaded.',
        loadFailed: 'Player medals could not be loaded. Please reload.',
        saveFailed: 'The action was not saved. Check the parameters and permissions, then retry.',
    } },
};
const { t, locale } = useI18n({ messages: i18nMessages });

watch([isStaff, viewing], () => {
    if (!isStaff.value || !viewing.value) {
        playerRequest += 1;
        catalogRequest += 1;
        player.value = null;
        loading.value = false;
        error.value = '';
        notice.value = '';
        return;
    }
    if (!catalogLoaded.value) void loadCatalog();
}, { immediate: true });
</script>

<style scoped>
.player-form,
.override-form {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: 8px;
    margin-bottom: 8px;
}

label {
    display: grid;
    gap: 4px;
    width: 280px;
    max-width: 100%;
}

.help {
    width: 100%;
    margin: 0;
}

input[type='date'] {
    color: var(--ui-text-color-primary);
    background: var(--ui-bg-color);
    border: 1px solid var(--ui-border-color);
}
</style>
