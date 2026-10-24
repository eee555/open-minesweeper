<template>
    <section class="video-deletion">
        <h2 class="text text-large">
            站长：批量删除录像
        </h2>
        <p v-if="checking" role="status">
            正在验证站长权限…
        </p>
        <template v-else-if="!authorized">
            <p role="alert" data-cy="delete-access-error">
                {{ accessError }}
            </p>
            <BaseButton data-cy="delete-check-access" @click="checkAccess">
                重新验证权限
            </BaseButton>
        </template>
        <template v-else>
            <p class="text-warning" data-cy="delete-warning">
                录像和文件删除后无法恢复。本次操作不会自动重算比赛；之后重算打卡赛或 GSC 录像来源成绩时，被删录像不再计分。GSC 手工成绩保留，但名次和积分可能变化。目前不自动通知比赛主办方。
            </p>
            <form @submit.prevent="run">
                <label for="video-deletion-ids">录像 ID</label>
                <textarea id="video-deletion-ids" v-model="input" :disabled="working" placeholder="用空格、逗号或换行分隔 ID，也可粘贴 JSON 数组。重复 ID 会去重。" data-cy="delete-ids" />
                <p v-if="input.trim() && !parsedIds.length" class="text-danger" role="alert">
                    请输入有效的正整数 ID；任意一项无效时均不会开始删除。
                </p>
                <label class="video-deletion-confirm">
                    <input v-model="confirmed" type="checkbox" :disabled="working" data-cy="delete-confirm">
                    我已阅读上述警告，确认永久删除所填录像。
                </label>
                <div class="video-deletion-actions">
                    <BaseButton native-type="submit" type="danger" :loading="working" :disabled="!canSubmit" data-cy="delete-start">
                        <template v-if="initialized">
                            继续删除剩余 {{ pending.length }} 个录像
                        </template>
                        <template v-else>
                            依次删除 {{ parsedIds.length }} 个录像
                        </template>
                    </BaseButton>
                    <BaseButton v-if="working" :disabled="stopRequested" data-cy="delete-stop" @click="stopRequested = true">
                        完成当前请求后停止
                    </BaseButton>
                </div>
            </form>
        </template>
        <p v-if="error" class="text-danger" role="alert" data-cy="delete-error">
            {{ error }}
        </p>
        <template v-if="initialized">
            <output aria-live="polite" data-cy="delete-progress">已确认 {{ results.length }} / {{ total }}：删除 {{ deletedCount }}，已不存在 {{ results.length - deletedCount }}</output>
            <p v-if="working && pending.length" role="status" data-cy="delete-current">
                正在处理录像 {{ pending[0] }}
            </p>
            <BaseTable :empty="!results.length" empty-text="暂无已确认结果" :column-count="3" data-cy="delete-results">
                <template #head>
                    <tr><th>ID</th><th>结果</th><th>受影响比赛 ID</th></tr>
                </template>
                <tr v-for="result in results" :key="result.id">
                    <td>{{ result.id }}</td><td>{{ result.deleted ? '已删除' : '已不存在' }}</td><td>{{ result.affected_tournament_ids.join(', ') || '—' }}</td>
                </tr>
            </BaseTable>
        </template>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { deleteVideosSequentially, fetchVideoDeletionAccess, parseVideoDeletionIds } from '@/services/videoDeletionService';
import type { VideoDeletionResult } from '@/services/videoDeletionService';
import '@/styles/text.css';

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
        accessError.value = isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403) ? '仅已登录的 superuser 可使用此页面，普通管理员无权访问。' : '权限验证失败，请稍后重试。';
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
        error.value = `录像 ${pending.value[0]} 请求失败：${String(reason)}。本条结果可能未知，后续请求已停止；请先核对，再确认并继续。`;
        confirmed.value = false;
        if (isAxiosError(reason) && (reason.response?.status === 401 || reason.response?.status === 403)) {
            authorized.value = false;
            accessError.value = '登录权限或 CSRF 校验失败，请重新验证权限。';
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
