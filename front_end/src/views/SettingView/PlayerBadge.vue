<template>
    <section class="card" data-cy="player-badge-settings">
        <h2 class="card-title">
            {{ t('local.playerBadge') }}
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
                                <option value="name1">{{ t('local.name1') }}</option>
                                <option value="name1 (name2)">{{ t('local.name1') }} ({{ t('local.name2') }})</option>
                            </select>
                        </label>
                        <label v-for="slot in playerNameSlots" v-show="slot === 'playerName1' || local.playerNameFormat === 'name1 (name2)'" :key="slot">
                            {{ t(slot === 'playerName1' ? 'local.name1' : 'local.name2') }}
                            <select v-model="local[slot]" class="player-name-select" :aria-label="t(slot === 'playerName1' ? 'local.name1' : 'local.name2')" :data-cy="slot === 'playerName1' ? 'player-name-1' : 'player-name-2'">
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
                        <span class="radio-buttons" role="radiogroup" :aria-label="t('local.nameFormat')" :title="t('local.nameFormatTooltip')" data-cy="player-name-order">
                            <label class="radio-button">
                                <input v-model="local.nameFormat" class="radio-button-input" type="radio" :name="nameOrderRadioName" value="first-last">
                                <span class="radio-button-content">{{ t('local.nameFormatFirstLast') }}</span>
                            </label>
                            <label class="radio-button">
                                <input v-model="local.nameFormat" class="radio-button-input" type="radio" :name="nameOrderRadioName" value="last-first">
                                <span class="radio-button-content">{{ t('local.nameFormatLastFirst') }}</span>
                            </label>
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

import { useId } from 'vue';
import { useI18n } from 'vue-i18n';

import { local } from '@/store/local';

const playerNameSlots = ['playerName1', 'playerName2'] as const;
const nameOrderRadioName = `name-order-${useId()}`;

const i18nMessages = {
    'zh-cn': { local: {
        playerBadge: '玩家名牌',
        name1: '名称1',
        name2: '名称2',
        nameFormat: '英文名格式',
        nameFormatFirstLast: '名 姓',
        nameFormatLastFirst: '姓, 名',
        nameFormatTooltip: '英文名显示格式',
        playerAvatar: '显示玩家头像',
        playerNameFormat: '名字格式化规则',
    } },
    en: { local: {
        playerBadge: 'Player Badge',
        name1: 'name1',
        name2: 'name2',
        nameFormat: 'International name format',
        nameFormatFirstLast: 'Given Family',
        nameFormatLastFirst: 'Family, Given',
        nameFormatTooltip: 'Display format for international names',
        playerAvatar: 'Show player avatars',
        playerNameFormat: 'Player name format',
    } },
    es: { local: {
        playerBadge: 'Insignia de jugador',
        name1: 'nombre1',
        name2: 'nombre2',
        nameFormat: 'Formato internacional para nombres',
        nameFormatFirstLast: 'Nombre Apellido',
        nameFormatLastFirst: 'Apellido, Nombre',
        nameFormatTooltip: 'Formato de visualización para nombres internacionales',
        playerAvatar: 'Mostrar avatares del jugador',
        playerNameFormat: 'Formato del nombre del jugador',
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
