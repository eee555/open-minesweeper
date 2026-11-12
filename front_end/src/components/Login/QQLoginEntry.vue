<template>
    <!-- 腾讯官方 16×16 标准标识原样使用；文字按合规要求固定中文，不随界面语言切换。 -->
    <button type="button" class="qq-login-entry" :class="{ 'qq-login-entry--compact': compact }" :aria-label="label" @keydown.stop @click.stop="notifyPending">
        <img :src="badge" alt="" width="16" height="16">
        <span class="qq-login-label">{{ label }}</span>
    </button>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';

defineProps({ compact: { type: Boolean, default: false } });

const badge = `${import.meta.env.BASE_URL}img/qq_login_16x16.png`;
// 审核 UI 规范要求文字含「QQ登录 / QQ / 登录」字样，故固定中文、不做本地化。
const label = 'QQ登录';
const pending = 'QQ 登录尚未开放，请先使用站内账号登录或注册。';

function notifyPending() {
    ElMessage.info(pending);
}
</script>

<style scoped lang="less">
.qq-login-entry {
    align-items: center;
    background: none;
    border: 0;
    border-top: 1px solid var(--el-border-color-lighter);
    color: inherit;
    cursor: pointer;
    display: flex;
    font: inherit;
    gap: 0.375rem;
    padding: 0.75rem 0 0;
    width: 100%;
}

// 菜单栏形态复用 .navigation-control 的整行布局，保持与相邻菜单项同样的行高与纵向居中。
.qq-login-entry--compact {
    border-top: 0;
    box-sizing: border-box;
    gap: 6px;
    height: 100%;
    padding: 0 10px;
}

.qq-login-entry:hover {
    color: var(--el-color-primary);
}

.qq-login-entry--compact:hover {
    background: var(--ui-fill-color-light);
    color: inherit;
}

.qq-login-entry:focus-visible {
    outline: 2px solid var(--el-color-primary);
    outline-offset: 2px;
}

.qq-login-entry img {
    display: block;
    height: 16px;
    width: 16px;
}

.qq-login-label {
    font-size: 0.875rem;
    line-height: 1.25;
    white-space: nowrap;
}

.qq-login-entry--compact .qq-login-label {
    font-size: inherit;
    line-height: 1.4;
}
</style>
