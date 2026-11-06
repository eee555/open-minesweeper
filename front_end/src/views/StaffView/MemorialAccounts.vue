<template>
    <section class="memorial-upload">
        <h1>纪念账号补录像</h1>
        <p>账号建档、旧数据清理及资料修改在服务器上通过管理命令或 Django shell 完成。</p>
        <p v-if="error" role="alert" class="text-danger">
            {{ error }}
        </p>
        <fieldset :disabled="busy || uploads.length > 0">
            <legend>目标账号</legend>
            <label>本站用户 ID <input v-model.number="queryId" type="number" min="1" data-cy="memorial-query-id"></label>
            <BaseButton :disabled="!positiveId(queryId)" @click="loadTarget">
                加载纪念账号
            </BaseButton>
        </fieldset>
        <template v-if="access">
            <h2>{{ access.user.realname || access.user.username }} #{{ access.user.id }}（UserMS #{{ access.user.userms_id }}）</h2>
            <RouterLink :to="`/player/${access.user.id}`" class="link">
                查看公开主页
            </RouterLink>
            <fieldset :disabled="busy || linkBusy" data-cy="memorial-links">
                <legend>账号关联</legend>
                <p>纪念账号无法登录，由站长直接指定扫雷网、MSGames、Minesweeper.Online 的外部账号。指定后该账号参与对应平台的排行与勋章计算。</p>
                <label>
                    平台
                    <select v-model="linkPlatform" data-cy="memorial-link-platform">
                        <option v-for="platform in assignablePlatforms" :key="platform.value" :value="platform.value">{{ platform.label }}</option>
                    </select>
                </label>
                <label>
                    平台 ID
                    <input v-model.trim="linkIdentifier" inputmode="numeric" data-cy="memorial-link-identifier">
                </label>
                <BaseButton :disabled="!canAssignLink" data-cy="memorial-link-assign" @click="assignLink">
                    设置关联
                </BaseButton>
                <ul data-cy="memorial-link-list">
                    <li v-for="link in links" :key="link.platform">
                        {{ platformLabel(link.platform) }} #{{ link.identifier }}{{ link.name ? `（${link.name}）` : '' }}
                        <BaseButton :disabled="linkBusy" data-cy="memorial-link-remove" @click="removeLink(link.platform)">
                            解除
                        </BaseButton>
                    </li>
                </ul>
                <p v-if="!links.length">
                    尚未设置任何账号关联。
                </p>
            </fieldset>
            <p>所选标识随首个文件请求提交，后端先逐个尝试绑定，再上传录像；绑定失败仍继续上传。录入错误请使用站长删除录像页面后重传。</p>
            <fieldset :disabled="busy" data-cy="memorial-upload-controls">
                <legend>选择文件和标识</legend>
                <input type="file" accept=".avf,.evf,.rmv,.mvf" multiple :disabled="uploads.length > 0" aria-label="选择纪念录像" data-cy="memorial-files" @change="selectFiles">
                <label data-cy="memorial-upload-anchor">上传时间锚点 <ElDatePicker v-model="anchor" type="datetime" :disabled="uploads.length > 0" /></label>
                <p>所有标识默认不选，请逐个勾选。最后一局采用锚点时间，之前各局按耗时倒推。</p>
                <label v-for="identifier in identifiers" :key="identifier" class="identifier-option">
                    <input v-model="selectedIdentifiers" type="checkbox" :value="identifier" :disabled="uploads.length > 0" data-cy="memorial-identifier">{{ identifier || '（空标识）' }}
                </label>
                <BaseButton :disabled="!canUpload" data-cy="memorial-upload-submit" @click="upload">
                    {{ uploads.length ? '重试未成功的录像' : '绑定标识并上传所选录像' }}
                </BaseButton>
                <BaseButton @click="resetBatch">
                    清空本批文件和标识
                </BaseButton>
            </fieldset>
            <ul>
                <li v-for="issue in parseIssues" :key="issue">
                    {{ issue }}
                </li>
            </ul>
            <ul data-cy="memorial-bindings">
                <li v-for="binding in bindings" :key="binding.identifier">
                    {{ binding.identifier || '（空标识）' }}：{{ binding.bound ? '已绑定' : binding.error || '归属冲突，未绑定；录像仍会上传' }}
                </li>
            </ul>
            <p v-if="completed">
                本批录像已全部上传。单独修正标识可在服务器上使用既有绑定服务处理。
            </p>
            <fieldset v-if="saoleiAccountId" data-cy="memorial-saolei-import">
                <legend>扫雷网录像导入</legend>
                <p>同步与导入由管理员代为执行；资料刷新与自动同步开关仍由站长在纪念账号页管理。</p>
                <VideoImportQueue :saolei-id="saoleiAccountId" owner />
            </fieldset>
            <p v-else>
                先在“账号关联”中设置扫雷网账号，之后可以在这里同步并导入其录像。
            </p>
            <BaseTable v-if="uploads.length" data-cy="memorial-upload-results">
                <template #head>
                    <tr><th>文件</th><th>标识</th><th>计划上传时间</th><th>实际上传时间</th><th>结果</th></tr>
                </template>
                <tr v-for="entry in uploads" :key="entry.index">
                    <td>{{ entry.file.name }}</td><td>{{ entry.identifier }}</td><td>{{ entry.uploadTime.toISOString() }}</td><td>{{ entry.result?.upload_time ?? '—' }}</td><td>{{ entry.result ? `录像 #${entry.result.id} / ${entry.result.state}` : entry.error || '待上传' }}</td>
                </tr>
            </BaseTable>
        </template>
        <p v-if="busy" role="status">
            正在处理，请等待本次请求完成。
        </p>
    </section>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus.css';
import { ElDatePicker } from 'element-plus';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import VideoImportQueue from '@/components/accountlinks/VideoImportQueue.vue';
import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { assignMemorialLink, fetchMemorialAccess, fetchMemorialLinks, memorialErrorText, planMemorialUploads, removeMemorialLink, uploadMemorialBatch } from '@/services/memorialService';
import type { MemorialAccess, MemorialAccountLink, MemorialBinding, MemorialReplay, MemorialUpload } from '@/services/memorialService';
import { extract_stat, load_video_file } from '@/utils/fileIO';

const assignablePlatforms = [
    { value: 'c', label: '扫雷网' },
    { value: 'a', label: 'MSGames' },
    { value: 'w', label: 'Minesweeper.Online' },
] as const;

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
const linkPlatform = ref<string>(assignablePlatforms[0]?.value ?? '');
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

const platformLabel = (value: string) => assignablePlatforms.find((platform) => platform.value === value)?.label ?? value;

async function act(callback: () => Promise<void>) {
    if (busy.value) return;
    busy.value = true;
    error.value = '';
    try {
        await callback();
    } catch (reason) {
        error.value = memorialErrorText(reason);
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
        error.value = memorialErrorText(reason);
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
        error.value = memorialErrorText(reason);
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
                    if (!video.is_completed || !stat.end_time || !Number.isFinite(stat.end_time.getTime()) || !Number.isSafeInteger(stat.timems) || stat.timems <= 0) throw new Error('录像未完成，或完成时间、耗时无效');
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
