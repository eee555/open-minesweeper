<template>
    <section class="card" data-cy="player-badge-settings">
        <h2 class="card-title">
            Player Badge
        </h2>
        <div class="description-layout">
            <dl class="descriptions">
                <div class="description-item">
                    <dt><label for="player-name-show-avatar">{{ t('local.playerAvatar') }}</label></dt>
                    <dd>
                        <input id="player-name-show-avatar" v-model="local.playerNameShowAvatar" class="checkbox-input" type="checkbox" data-cy="player-name-show-avatar">
                    </dd>
                </div>
                <div class="description-item description-wide">
                    <dt>{{ t('local.playerNameFormat') }}</dt>
                    <dd class="player-name-settings">
                        <label>
                            {{ t('prop.format') }}
                            <select v-model="local.playerNameFormat" class="player-name-select" :aria-label="t('local.playerNameFormat')" data-cy="player-name-format">
                                <option value="name1">name1</option>
                                <option value="name1 (name2)">name1 (name2)</option>
                            </select>
                        </label>
                        <label v-for="slot in playerNameSlots" v-show="slot === 'playerName1' || local.playerNameFormat === 'name1 (name2)'" :key="slot">
                            {{ slot === 'playerName1' ? 'name1' : 'name2' }}
                            <select v-model="local[slot]" class="player-name-select" :aria-label="slot === 'playerName1' ? 'name1' : 'name2'" :data-cy="slot === 'playerName1' ? 'player-name-1' : 'player-name-2'">
                                <option value="realname">{{ t('prop.localName') }}</option>
                                <option value="international">{{ t('prop.internationalName') }}</option>
                                <option value="username">{{ t('form.username') }}</option>
                            </select>
                        </label>
                    </dd>
                </div>
                <div class="description-item">
                    <dt>{{ t('local.nameFormat') }}</dt>
                    <dd>
                        <span :title="t('local.nameFormatTooltip')">
                            <ElRadioGroup v-model="local.nameFormat" size="small" style="vertical-align: middle;">
                                <ElRadioButton :label="t('local.nameFormatFirstLast')" value="first-last" />
                                <ElRadioButton :label="t('local.nameFormatLastFirst')" value="last-first" />
                            </ElRadioGroup>
                        </span>
                    </dd>
                </div>
            </dl>
        </div>
    </section>
</template>

<script setup lang="ts">
import '@/styles/descriptions.css';
import '@/styles/cards.css';

import { ElRadioButton, ElRadioGroup } from 'element-plus';
import { useI18n } from 'vue-i18n';

import { local } from '@/store/local';

const playerNameSlots = ['playerName1', 'playerName2'] as const;

const i18nMessages = {
    'zh-cn': { local: {
        nameFormat: '英文名格式',
        nameFormatFirstLast: '名 姓',
        nameFormatLastFirst: '姓, 名',
        nameFormatTooltip: '英文名显示格式',
        playerAvatar: '显示玩家头像',
        playerNameFormat: '名字格式化规则',
    } },
    en: { local: {
        nameFormat: 'International name format',
        nameFormatFirstLast: 'Given Family',
        nameFormatLastFirst: 'Family, Given',
        nameFormatTooltip: 'Display format for international names',
        playerAvatar: 'Show player avatars',
        playerNameFormat: 'Player name format',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.player-name-select {
    min-height: 28px;
    max-width: 100%;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    padding: 3px 8px;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.player-name-select:focus-visible {
    outline: 2px solid var(--ui-color-primary);
    outline-offset: 1px;
}

.player-name-settings,
.player-name-settings label {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
}

.player-name-settings {
    gap: 8px;
}
</style>
