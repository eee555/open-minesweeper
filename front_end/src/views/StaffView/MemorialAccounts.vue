<template>
    <section class="memorial-upload">
        <h1>{{ t('local.memorialTitle') }}</h1>
        <p>{{ t('local.memorialHint') }}</p>
        <p v-if="error" role="alert" class="text-danger">
            {{ error }}
        </p>
        <fieldset :disabled="busy || uploads.length > 0">
            <legend>{{ t('local.target') }}</legend>
            <label>{{ t('local.siteId') }} <input v-model.number="queryId" type="number" min="1" data-cy="memorial-query-id"></label>
            <BaseButton :disabled="!positiveId(queryId)" @click="loadTarget">
                {{ t('local.loadMemorial') }}
            </BaseButton>
        </fieldset>
        <template v-if="access">
            <h2>{{ access.user.realname || access.user.username }} #{{ access.user.id }}（UserMS #{{ access.user.userms_id }}）</h2>
            <RouterLink :to="`/player/${access.user.id}`" class="link">
                {{ t('local.publicProfile') }}
            </RouterLink>
            <fieldset :disabled="busy || linkBusy" data-cy="memorial-links">
                <legend>{{ t('local.links') }}</legend>
                <p>{{ t('local.memorialLinks') }}</p>
                <label>
                    {{ t('local.platform') }}
                    <select v-model="linkPlatform" data-cy="memorial-link-platform">
                        <option v-for="platform in assignablePlatforms" :key="platform.value" :value="platform.value">{{ platform.label }}</option>
                    </select>
                </label>
                <label>
                    {{ t('local.platformId') }}
                    <input v-model.trim="linkIdentifier" inputmode="numeric" data-cy="memorial-link-identifier">
                </label>
                <BaseButton :disabled="!canAssignLink" data-cy="memorial-link-assign" @click="assignLink">
                    {{ t('local.assign') }}
                </BaseButton>
                <ul data-cy="memorial-link-list">
                    <li v-for="link in links" :key="link.platform">
                        {{ platformLabel(link.platform) }} #{{ link.identifier }}{{ link.name ? `（${link.name}）` : '' }}
                        <BaseButton :disabled="linkBusy" data-cy="memorial-link-remove" @click="removeLink(link.platform)">
                            {{ t('local.unlink') }}
                        </BaseButton>
                    </li>
                </ul>
                <p v-if="!links.length">
                    {{ t('local.noLinks') }}
                </p>
            </fieldset>
            <p>{{ t('local.bindingHint') }}</p>
            <fieldset :disabled="busy" data-cy="memorial-upload-controls">
                <legend>{{ t('local.filesAndIds') }}</legend>
                <input type="file" accept=".avf,.evf,.rmv,.mvf" multiple :disabled="uploads.length > 0" :aria-label="t('local.chooseMemorial')" data-cy="memorial-files" @change="selectFiles">
                <label data-cy="memorial-upload-anchor">{{ t('local.anchor') }} <ElDatePicker v-model="anchor" type="datetime" :disabled="uploads.length > 0" /></label>
                <p>{{ t('local.anchorHint') }}</p>
                <label v-for="identifier in identifiers" :key="identifier" class="identifier-option">
                    <input v-model="selectedIdentifiers" type="checkbox" :value="identifier" :disabled="uploads.length > 0" data-cy="memorial-identifier">{{ identifier || t('local.emptyId') }}
                </label>
                <BaseButton :disabled="!canUpload" data-cy="memorial-upload-submit" @click="upload">
                    {{ uploads.length ? t('local.retryUploads') : t('local.bindSelected') }}
                </BaseButton>
                <BaseButton @click="resetBatch">
                    {{ t('local.clearBatch') }}
                </BaseButton>
            </fieldset>
            <ul>
                <li v-for="issue in parseIssues" :key="issue">
                    {{ issue }}
                </li>
            </ul>
            <ul data-cy="memorial-bindings">
                <li v-for="binding in bindings" :key="binding.identifier">
                    {{ binding.identifier || t('local.emptyId') }}：{{ binding.bound ? t('local.bound') : t(binding.error ? 'local.bindFailed' : 'local.bindConflict') }}
                </li>
            </ul>
            <p v-if="completed">
                {{ t('local.batchDone') }}
            </p>
            <fieldset v-if="saoleiAccountId" data-cy="memorial-saolei-import">
                <legend>{{ t('local.importSaolei') }}</legend>
                <p>{{ t('local.syncHint') }}</p>
                <VideoImportQueue :saolei-id="saoleiAccountId" owner />
            </fieldset>
            <p v-else>
                {{ t('local.linkFirst') }}
            </p>
            <BaseTable v-if="uploads.length" data-cy="memorial-upload-results">
                <template #head>
                    <tr><th>{{ t('local.file') }}</th><th>{{ t('local.identifier') }}</th><th>{{ t('local.planned') }}</th><th>{{ t('local.actual') }}</th><th>{{ t('local.result') }}</th></tr>
                </template>
                <tr v-for="entry in uploads" :key="entry.index">
                    <td>{{ entry.file.name }}</td><td>{{ entry.identifier }}</td><td>{{ entry.uploadTime.toISOString() }}</td><td>{{ entry.result?.upload_time ?? '—' }}</td><td>{{ entry.result ? t('local.replayResult', { id: entry.result.id, state: entry.result.state }) : t(entry.errorCode ? `memorialError.${entry.errorCode}` : 'local.pending') }}</td>
                </tr>
            </BaseTable>
        </template>
        <p v-if="busy" role="status">
            {{ t('local.working') }}
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus.css';
import { ElDatePicker } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute } from 'vue-router';

import VideoImportQueue from '@/components/accountlinks/VideoImportQueue.vue';
import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { historyErrorText } from '@/i18n/historyErrorText';
import { assignMemorialLink, fetchMemorialAccess, fetchMemorialLinks, memorialErrorCode, planMemorialUploads, removeMemorialLink, uploadMemorialBatch } from '@/services/memorialService';
import type { MemorialAccess, MemorialAccountLink, MemorialBinding, MemorialReplay, MemorialUpload } from '@/services/memorialService';
import { extract_stat, load_video_file } from '@/utils/fileIO';
import { HistoryImportError } from '@/utils/historyImportError';

const i18nMessages = {
    'zh-cn': { local: {
        replayResult: '录像 #{id} / {state}',
        memorialLinks: '纪念账号无法登录，由站长直接指定扫雷网、MSGames、Minesweeper.Online 的外部账号。指定后该账号参与对应平台的排行与勋章计算。',
        bindingHint: '所选标识随首个文件请求提交，后端先逐个尝试绑定，再上传录像；绑定失败仍继续上传。录入错误请使用站长删除录像页面后重传。',
        memorialHint: '账号建档、旧数据清理及资料修改在服务器上通过管理命令或 Django shell 完成。',
        syncHint: '同步与导入由管理员代为执行；资料刷新与自动同步开关仍由站长在纪念账号页管理。',
        anchorHint: '所有标识默认不选，请逐个勾选。最后一局采用锚点时间，之前各局按耗时倒推。',
        batchDone: '本批录像已全部上传。单独修正标识可在服务器上使用既有绑定服务处理。',
        linkFirst: '先在“账号关联”中设置扫雷网账号，之后可以在这里同步并导入其录像。',
        invalidReplay: '录像未完成，或完成时间、耗时无效',
        bindConflict: '归属冲突，未绑定；录像仍会上传',
        bindFailed: '标识绑定失败，录像仍会上传',
        working: '正在处理，请等待本次请求完成。',
        noLinks: '尚未设置任何账号关联。',
        bindSelected: '绑定标识并上传所选录像',
        clearBatch: '清空本批文件和标识',
        retryUploads: '重试未成功的录像',
        memorialTitle: '纪念账号补录像',
        siteId: '本站用户 ID',
        filesAndIds: '选择文件和标识',
        importSaolei: '扫雷网录像导入',
        anchor: '上传时间锚点',
        loadMemorial: '加载纪念账号',
        publicProfile: '查看公开主页',
        chooseMemorial: '选择纪念录像',
        planned: '计划上传时间',
        actual: '实际上传时间',
        platformId: '平台 ID',
        emptyId: '（空标识）',
        target: '目标账号',
        links: '账号关联',
        assign: '设置关联',
        saolei: '扫雷网',
        bound: '已绑定',
        pending: '待上传',
        file: '文件',
        identifier: '标识',
        result: '结果',
        platform: '平台',
        unlink: '解除',
    } },
    en: { local: {
        replayResult: 'Replay #{id} / {state}',
        memorialLinks: 'Memorial accounts cannot sign in. A superuser assigns their Saolei.wang, MSGames or Minesweeper.Online accounts. Linked accounts count toward that platform’s rankings and medals.',
        bindingHint: 'Selected identifiers are sent with the first file. Each link is attempted before upload. A failed link does not stop uploads. Correct mistakes by deleting the replay on the superuser page and uploading it again.',
        memorialHint: 'Create accounts, clean up old data and edit profiles on the server using management commands or the Django shell.',
        syncHint: 'Moderators perform synchronization and imports. The superuser manages profile refreshes and automatic synchronization on the memorial account page.',
        anchorHint: 'Select identifiers individually. The last replay uses the reference time. Earlier times are calculated backwards from game durations.',
        batchDone: 'All replays in this batch were uploaded. Individual identifiers can be corrected on the server using the binding service.',
        linkFirst: 'Link a Saolei.wang account under Account links before synchronizing and importing its replays here.',
        invalidReplay: 'Unfinished replay or invalid finish time or duration',
        bindConflict: 'Ownership conflict. Replay uploads will continue without linking.',
        bindFailed: 'Could not link the identifier. Replay uploads will continue.',
        working: 'Processing. Wait for this request to finish.',
        noLinks: 'No accounts linked yet.',
        bindSelected: 'Link identifiers and upload selected replays',
        clearBatch: 'Clear this batch of files and identifiers',
        retryUploads: 'Retry unsuccessful uploads',
        memorialTitle: 'Add replays to a memorial account',
        siteId: 'Site user ID',
        filesAndIds: 'Select files and identifiers',
        importSaolei: 'Import Saolei.wang replays',
        anchor: 'Reference upload time',
        loadMemorial: 'Load memorial account',
        publicProfile: 'View public profile',
        chooseMemorial: 'Choose memorial replays',
        planned: 'Planned upload time',
        actual: 'Actual upload time',
        platformId: 'Platform ID',
        emptyId: '(empty identifier)',
        target: 'Target account',
        links: 'Account links',
        assign: 'Link account',
        saolei: 'Saolei.wang',
        bound: 'Linked',
        pending: 'Pending upload',
        file: 'File',
        identifier: 'Identifier',
        result: 'Result',
        platform: 'Platform',
        unlink: 'Unlink',
    } },
    es: { local: {
        replayResult: 'Repetición #{id} / {state}',
        memorialLinks: 'Las cuentas conmemorativas no pueden iniciar sesión. El superusuario asigna sus cuentas de Saolei.wang, MSGames o Minesweeper.Online para que cuenten en las clasificaciones y medallas de la plataforma correspondiente.',
        bindingHint: 'Los identificadores se envían con el primer archivo. Se intenta vincular cada uno antes de la subida, que continúa aunque alguna vinculación falle. Si te equivocas, elimina la repetición en la página de superusuario y vuelve a subirla.',
        memorialHint: 'Para crear cuentas, limpiar datos antiguos o modificar perfiles, usa los comandos de administración o la consola de Django en el servidor.',
        syncHint: 'Los moderadores se encargan de sincronizar e importar. El superusuario gestiona la actualización del perfil y la sincronización automática en la página de la cuenta conmemorativa.',
        anchorHint: 'Marca los identificadores uno a uno. La última partida recibe la fecha de referencia. Las anteriores se calculan hacia atrás a partir de su duración.',
        batchDone: 'Se han subido todas las repeticiones del lote. Puedes corregir identificadores individuales con el servicio de vinculación del servidor.',
        linkFirst: 'Vincula primero la cuenta de Saolei.wang en «Cuentas vinculadas». Después podrás sincronizar e importar sus repeticiones aquí.',
        invalidReplay: 'Partida sin terminar, fecha de finalización o duración no válidas',
        bindConflict: 'Conflicto de titularidad. Las repeticiones se subirán sin vincular el identificador.',
        bindFailed: 'No se pudo vincular el identificador. Las repeticiones se seguirán subiendo.',
        working: 'Procesando. Espera a que termine la solicitud.',
        noLinks: 'Aún no hay cuentas vinculadas.',
        bindSelected: 'Vincular los identificadores y subir las repeticiones seleccionadas',
        clearBatch: 'Vaciar los archivos e identificadores del lote',
        retryUploads: 'Reintentar las subidas fallidas',
        memorialTitle: 'Añadir repeticiones a una cuenta conmemorativa',
        siteId: 'ID de usuario del sitio',
        filesAndIds: 'Seleccionar archivos e identificadores',
        importSaolei: 'Importar repeticiones de Saolei.wang',
        anchor: 'Fecha de referencia para la subida',
        loadMemorial: 'Cargar cuenta conmemorativa',
        publicProfile: 'Ver perfil público',
        chooseMemorial: 'Seleccionar repeticiones conmemorativas',
        planned: 'Fecha de subida prevista',
        actual: 'Fecha de subida real',
        platformId: 'ID en la plataforma',
        emptyId: '(identificador vacío)',
        target: 'Cuenta de destino',
        links: 'Cuentas vinculadas',
        assign: 'Vincular cuenta',
        saolei: 'Saolei.wang',
        bound: 'Vinculado',
        pending: 'Pendiente de subida',
        file: 'Archivo',
        identifier: 'Identificador',
        result: 'Resultado',
        platform: 'Plataforma',
        unlink: 'Desvincular',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const assignablePlatforms = computed(() => [
    { value: 'c', label: t('local.saolei') },
    { value: 'a', label: 'MSGames' },
    { value: 'w', label: 'Minesweeper.Online' },
] as const);

const route = useRoute();
const busy = ref(false);
const error = ref('');
const access = ref<MemorialAccess>();
const queryId = ref(Number(route.query.id) || undefined);
const anchor = ref<Date | null>(null);
const replays = ref<MemorialReplay[]>([]);
const selectedIdentifiers = ref<string[]>([]);
const parseIssues = ref<string[]>([]);
const bindings = ref<MemorialBinding[]>([]);
const uploads = ref<MemorialUpload[]>([]);
const links = ref<MemorialAccountLink[]>([]);
const linkToken = ref('');
const linkPlatform = ref<string>(assignablePlatforms.value[0]?.value ?? '');
const linkIdentifier = ref('');
const linkBusy = ref(false);
const saoleiAccountId = ref<number>();
const identifiers = computed(() => [...new Set(replays.value.map((replay) => replay.identifier))]);
const completed = computed(() => uploads.value.length > 0 && uploads.value.every((entry) => entry.result !== undefined));
const positiveId = (id: unknown): id is number => typeof id === 'number' && Number.isSafeInteger(id) && id > 0;
const canUpload = computed(() => !busy.value && !completed.value && !!access.value && selectedIdentifiers.value.length > 0 && !!anchor.value);
const canAssignLink = computed(() => !linkBusy.value && !!access.value && positiveId(linkPlatform.value === '' ? undefined : Number(linkIdentifier.value)) && (/^[1-9][0-9]*$/).test(linkIdentifier.value));
let disposed = false;
onBeforeUnmount(() => {
    disposed = true;
});

function resetBatch() {
    replays.value = [];
    selectedIdentifiers.value = [];
    parseIssues.value = [];
    bindings.value = [];
    uploads.value = [];
}
watch(queryId, () => {
    access.value = undefined; resetBatch();
    links.value = []; linkToken.value = ''; linkIdentifier.value = ''; saoleiAccountId.value = undefined;
});

const platformLabel = (value: string) => assignablePlatforms.value.find((platform) => platform.value === value)?.label ?? value;

async function act(callback: () => Promise<void>) {
    if (busy.value) return;
    busy.value = true;
    error.value = '';
    try {
        await callback();
    } catch (reason) {
        error.value = reason instanceof HistoryImportError ? historyErrorText(reason) : t(`memorialError.${memorialErrorCode(reason)}`);
    } finally {
        busy.value = false;
    }
}
async function loadTarget() {
    if (!positiveId(queryId.value)) return;
    const id = queryId.value;
    access.value = undefined;
    links.value = [];
    linkToken.value = '';
    await act(async () => {
        access.value = await fetchMemorialAccess(id);
        const data = await fetchMemorialLinks(id);
        linkToken.value = data.csrf_token;
        links.value = data.links;
        const saolei = data.links.find((link) => link.platform === 'c');
        saoleiAccountId.value = saolei ? Number(saolei.identifier) : undefined;
    });
}

async function assignLink() {
    if (!access.value || !canAssignLink.value || !linkToken.value) return;
    const { id } = access.value.user;
    linkBusy.value = true;
    error.value = '';
    try {
        await assignMemorialLink(id, linkPlatform.value, linkIdentifier.value, linkToken.value);
        links.value = (await fetchMemorialLinks(id)).links;
        linkIdentifier.value = '';
    } catch (reason) {
        error.value = t(`memorialError.${memorialErrorCode(reason)}`);
    } finally {
        linkBusy.value = false;
    }
}

async function removeLink(platform: string) {
    if (!access.value || !linkToken.value) return;
    const { id } = access.value.user;
    linkBusy.value = true;
    error.value = '';
    try {
        await removeMemorialLink(id, platform, linkToken.value);
        links.value = (await fetchMemorialLinks(id)).links;
        if (platform === 'c') saoleiAccountId.value = undefined;
    } catch (reason) {
        error.value = t(`memorialError.${memorialErrorCode(reason)}`);
    } finally {
        linkBusy.value = false;
    }
}
async function selectFiles(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    resetBatch();
    await act(async () => {
        for (const [index, file] of files.entries()) {
            try {
                const video = load_video_file(await file.arrayBuffer(), file.name.toLowerCase());
                try {
                    const stat = extract_stat(video);
                    if (!video.is_completed || !stat.end_time || !Number.isFinite(stat.end_time.getTime()) || !Number.isSafeInteger(stat.timems) || stat.timems <= 0) throw new Error(t('local.invalidReplay'));
                    replays.value.push({ index, file, identifier: video.player_identifier, endTime: stat.end_time, timems: stat.timems });
                } finally {
                    video.free();
                }
            } catch (reason) {
                parseIssues.value.push(`${file.name}：${String(reason)}`);
            }
        }
    });
}
async function upload() {
    if (!canUpload.value || !access.value || !anchor.value) return;
    const { user, csrf_token: token } = access.value;
    const selected = [...selectedIdentifiers.value];
    const uploadAnchor = anchor.value;
    await act(async () => {
        if (!uploads.value.length) uploads.value = planMemorialUploads(replays.value, selected, uploadAnchor);
        await uploadMemorialBatch(user.id, selected, bindings.value, uploads.value, token, () => disposed);
    });
}
onMounted(async () => {
    if (positiveId(queryId.value)) await loadTarget();
});
</script>

<style scoped>
.memorial-upload {
    display: grid;
    gap: 0.5rem;
    padding: 0.5rem;
}
fieldset {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    border: 1px solid var(--el-border-color);
}
label {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}
input {
    color: var(--el-text-color-primary);
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color);
    border-radius: 0;
}
.identifier-option {
    overflow-wrap: anywhere;
}
</style>
