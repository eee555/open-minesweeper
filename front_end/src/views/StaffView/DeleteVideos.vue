<template>
    <section class="video-deletion">
        <h2 class="text text-large">
            {{ t('local.deletionTitle') }}
        </h2>
        <p v-if="checking" role="status">
            {{ t('local.checking') }}
        </p>
        <template v-else-if="!authorized">
            <p role="alert" data-cy="delete-access-error">
                {{ accessError }}
            </p>
            <BaseButton data-cy="delete-check-access" @click="checkAccess">
                {{ t('local.verifyAccess') }}
            </BaseButton>
        </template>
        <template v-else>
            <p class="text-warning" data-cy="delete-warning">
                {{ t('local.deleteWarning') }}
            </p>
            <form @submit.prevent="run">
                <label for="video-deletion-ids">{{ t('local.replayId') }}</label>
                <textarea id="video-deletion-ids" v-model="input" :disabled="working" :placeholder="t('local.idsHint')" data-cy="delete-ids" />
                <p v-if="input.trim() && !parsedIds.length" class="text-danger" role="alert">
                    {{ t('local.invalidIds') }}
                </p>
                <label class="video-deletion-confirm">
                    <input v-model="confirmed" type="checkbox" :disabled="working" data-cy="delete-confirm">
                    {{ t('local.confirmDeletion') }}
                </label>
                <div class="video-deletion-actions">
                    <BaseButton native-type="submit" type="danger" :loading="working" :disabled="!canSubmit" data-cy="delete-start">
                        <template v-if="initialized">
                            {{ t('local.resumeDeletion', { count: pending.length }) }}
                        </template>
                        <template v-else>
                            {{ t('local.deleteInOrder', { count: parsedIds.length }) }}
                        </template>
                    </BaseButton>
                    <BaseButton v-if="working" :disabled="stopRequested" data-cy="delete-stop" @click="stopRequested = true">
                        {{ t('local.stopAfterCurrent') }}
                    </BaseButton>
                </div>
            </form>
        </template>
        <p v-if="error" class="text-danger" role="alert" data-cy="delete-error">
            {{ error }}
        </p>
        <template v-if="initialized">
            <output aria-live="polite" data-cy="delete-progress">{{ t('local.deleteProgress', { done: results.length, total, deleted: deletedCount, missing: results.length - deletedCount }) }}</output>
            <p v-if="working && pending.length" role="status" data-cy="delete-current">
                {{ t('local.processing', { id: pending[0] }) }}
            </p>
            <BaseTable :empty="!results.length" :empty-text="t('local.emptyResults')" :column-count="3" data-cy="delete-results">
                <template #head>
                    <tr><th>ID</th><th>{{ t('local.result') }}</th><th>{{ t('local.affected') }}</th></tr>
                </template>
                <tr v-for="result in results" :key="result.id">
                    <td>{{ result.id }}</td><td>{{ result.deleted ? t('local.deleted') : t('local.missing') }}</td><td>{{ result.affected_tournament_ids.join(', ') || '—' }}</td>
                </tr>
            </BaseTable>
        </template>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { deleteVideosSequentially, fetchVideoDeletionAccess, parseVideoDeletionIds } from '@/services/videoDeletionService';
import type { VideoDeletionResult } from '@/services/videoDeletionService';

const i18nMessages = {
    'zh-cn': { local: {
        resumeDeletion: '继续删除剩余 {count} 个录像',
        deleteInOrder: '依次删除 {count} 个录像',
        deleteProgress: '已确认 {done} / {total}：删除 {deleted}，已不存在 {missing}',
        processing: '正在处理录像 {id}',
        deletionFailed: '录像 {id} 请求失败：{reason}。本条结果可能未知，后续请求已停止；请先核对，再确认并继续。',
        deleteWarning: '录像和文件删除后无法恢复。本次操作不会自动重算比赛；之后重算打卡赛或 GSC 录像来源成绩时，被删录像不再计分。GSC 手工成绩保留，但名次和积分可能变化。目前不自动通知比赛主办方。',
        idsHint: '用空格、逗号或换行分隔 ID，也可粘贴 JSON 数组。重复 ID 会去重。',
        superuserOnly: '仅已登录的 superuser 可使用此页面，普通管理员无权访问。',
        invalidIds: '请输入有效的正整数 ID；任意一项无效时均不会开始删除。',
        csrfFailed: '登录权限或 CSRF 校验失败，请重新验证权限。',
        confirmDeletion: '我已阅读上述警告，确认永久删除所填录像。',
        accessFailed: '权限验证失败，请稍后重试。',
        deletionTitle: '站长：批量删除录像',
        checking: '正在验证站长权限…',
        stopAfterCurrent: '完成当前请求后停止',
        affected: '受影响比赛 ID',
        emptyResults: '暂无已确认结果',
        verifyAccess: '重新验证权限',
        replayId: '录像 ID',
        missing: '已不存在',
        deleted: '已删除',
        result: '结果',
    } },
    en: { local: {
        resumeDeletion: 'Continue deleting the remaining {count} replays',
        deleteInOrder: 'Delete {count} replays in order',
        deleteProgress: 'Confirmed {done} / {total}: {deleted} deleted, {missing} already absent',
        processing: 'Processing replay {id}',
        deletionFailed: 'Request for replay {id} failed: {reason}. Its outcome is uncertain. Further requests have stopped. Check the result before confirming and continuing.',
        deleteWarning: 'Deleted replays and files cannot be recovered. Tournaments are not recalculated automatically. Deleted replays no longer count when weekly or GSC replay scores are recalculated. Manual GSC scores are kept, but rankings and points may change. Organizers are not notified automatically.',
        idsHint: 'Separate IDs with spaces, commas or newlines, or paste a JSON array. Duplicates are removed.',
        superuserOnly: 'This page requires a signed-in superuser.',
        invalidIds: 'Enter positive integer IDs. Deletion starts only when all IDs are valid.',
        csrfFailed: 'Session permissions or CSRF validation failed. Recheck permissions.',
        confirmDeletion: 'I have read the warning and confirm permanent deletion of the listed replays.',
        accessFailed: 'Could not verify permissions. Try again later.',
        deletionTitle: 'Superuser: bulk replay deletion',
        checking: 'Checking superuser permissions…',
        stopAfterCurrent: 'Stop after the current request',
        affected: 'Affected tournament IDs',
        emptyResults: 'No confirmed results yet',
        verifyAccess: 'Recheck permissions',
        replayId: 'Replay ID',
        missing: 'Already absent',
        deleted: 'Deleted',
        result: 'Result',
    } },
    es: { local: {
        resumeDeletion: 'Continuar la eliminación de las {count} repeticiones pendientes',
        deleteInOrder: 'Eliminar {count} repeticiones en orden',
        deleteProgress: 'Confirmadas {done} de {total}: {deleted} eliminadas, {missing} ya no existían',
        processing: 'Procesando la repetición {id}',
        deletionFailed: 'Falló la solicitud para la repetición {id}: {reason}. Comprueba si se eliminó antes de confirmar y continuar. Se han detenido las solicitudes siguientes.',
        deleteWarning: 'Las repeticiones y los archivos eliminados son irrecuperables. Los torneos no se recalculan automáticamente. Al recalcular los resultados de los torneos semanales o de la GSC, las repeticiones eliminadas dejarán de puntuar. Se conservarán las puntuaciones manuales de la GSC, pero podrán cambiar los puestos y los puntos. Los organizadores no recibirán un aviso automático.',
        idsHint: 'Separa los ID con espacios, comas o saltos de línea, o pega una lista JSON. Se omitirán los duplicados.',
        superuserOnly: 'Esta página requiere una sesión de superusuario.',
        invalidIds: 'Introduce ID enteros positivos. La eliminación solo comenzará si todos son válidos.',
        csrfFailed: 'Falló la comprobación de permisos de sesión o de CSRF. Vuelve a verificar los permisos.',
        confirmDeletion: 'He leído la advertencia y confirmo la eliminación permanente de las repeticiones indicadas.',
        accessFailed: 'No se pudieron verificar los permisos. Inténtalo más tarde.',
        deletionTitle: 'Superusuario: eliminación de repeticiones en lote',
        checking: 'Comprobando permisos de superusuario…',
        stopAfterCurrent: 'Detener tras la solicitud actual',
        affected: 'ID de los torneos afectados',
        emptyResults: 'Aún no hay resultados confirmados',
        verifyAccess: 'Volver a comprobar los permisos',
        replayId: 'ID de repetición',
        missing: 'Ya no existe',
        deleted: 'Eliminada',
        result: 'Resultado',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const checking = ref(true);
const authorized = ref(false);
const accessError = ref('');
const csrfToken = ref('');
const input = ref('');
const confirmed = ref(false);
const initialized = ref(false);
const working = ref(false);
const stopRequested = ref(false);
const pending = ref<number[]>([]);
const results = ref<VideoDeletionResult[]>([]);
const error = ref('');
let disposed = false;

const parsedIds = computed(() => {
    try {
        return parseVideoDeletionIds(input.value);
    } catch {
        return [];
    }
});
const total = computed(() => pending.value.length + results.value.length);
const deletedCount = computed(() => results.value.filter((result) => result.deleted).length);
const canSubmit = computed(() => authorized.value && confirmed.value && !working.value && (initialized.value ? pending.value.length > 0 : parsedIds.value.length > 0));

watch(input, () => {
    initialized.value = false;
    confirmed.value = false;
    pending.value = [];
    results.value = [];
    error.value = '';
});
onMounted(() => {
    void checkAccess();
});
onBeforeUnmount(() => {
    disposed = true;
    stopRequested.value = true;
});

async function checkAccess() {
    checking.value = true;
    authorized.value = false;
    try {
        const token = await fetchVideoDeletionAccess();
        if (disposed) return;
        csrfToken.value = token;
        authorized.value = true;
        accessError.value = '';
    } catch (reason) {
        accessError.value = isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403) ? t('local.superuserOnly') : t('local.accessFailed');
    } finally {
        checking.value = false;
    }
}

async function run() {
    if (!canSubmit.value) return;
    if (!initialized.value) {
        pending.value = [...parsedIds.value];
        results.value = [];
        initialized.value = true;
    }
    working.value = true;
    stopRequested.value = false;
    error.value = '';
    try {
        await deleteVideosSequentially([...pending.value], csrfToken.value, (result) => {
            results.value.push(result);
            pending.value.shift();
        }, () => disposed || stopRequested.value);
    } catch (reason) {
        error.value = t('local.deletionFailed', { id: pending.value[0], reason: String(reason) });
        confirmed.value = false;
        if (isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403)) {
            authorized.value = false;
            accessError.value = t('local.csrfFailed');
        }
    } finally {
        working.value = false;
    }
}
</script>

<style scoped>
.video-deletion,
form {
    display: grid;
    gap: 8px;
}

p {
    margin: 0;
}

textarea {
    width: 100%;
    min-height: 160px;
    box-sizing: border-box;
    padding: 6px;
    color: var(--ui-text-color-regular);
    background: var(--el-fill-color-blank);
    border: 1px solid var(--el-border-color);
    font-family: monospace;
}

.video-deletion-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
</style>
