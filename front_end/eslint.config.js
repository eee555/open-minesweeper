/* eslint-disable import-x/no-named-as-default-member */
import eslint from '@eslint/js';
import stylistic from '@stylistic/eslint-plugin';
import { defineConfig } from 'eslint/config';
import { createTypeScriptImportResolver } from 'eslint-import-resolver-typescript';
import pluginCypress from 'eslint-plugin-cypress';
import importPlugin from 'eslint-plugin-import-x';
import pluginVue from 'eslint-plugin-vue';
import globals from 'globals';
import tseslint from 'typescript-eslint';
// import vueI18n from '@intlify/eslint-plugin-vue-i18n'; // 不兼容ts。https://github.com/intlify/eslint-plugin-vue-i18n/issues/32

const restrictedHtmlElements = [{
    element: ['ElText', 'el-text'],
    message: 'Use "@/styles/text.css" instead.',
}, {
    element: ['ElContainer', 'el-container', 'ElHeader', 'el-header', 'ElMain', 'el-main', 'ElAside', 'el-aside', 'ElFooter', 'el-footer', 'ElRow', 'el-row', 'ElCol', 'el-col'],
    message: 'Use native HTML and CSS for layout; reuse "@/styles/layout.css" where appropriate.',
}, {
    element: ['ElCard', 'el-card'],
    message: 'Use "@/styles/cards.css" instead.',
}, {
    element: ['ElDivider', 'el-divider'],
    message: 'Use CSS borders on native containers instead.',
}, {
    element: ['ElCheckbox', 'el-checkbox', 'ElCheckboxGroup', 'el-checkbox-group', 'ElCheckboxButton', 'el-checkbox-button'],
    message: 'Use a native checkbox and associated label with "@/styles/checkbox.css" or "@/styles/checkbox-buttons.css" instead.',
}];

const restrictedActionElements = [{
    element: ['ElButton', 'el-button'],
    message: 'Use BaseButton or a native button with "@/styles/button.css" instead.',
}, {
    element: ['ElLink', 'el-link'],
    message: 'Use a native link with "@/styles/link.css" for navigation, or BaseTextButton for actions.',
}];

const restrictedDescriptionsElements = [{
    element: ['ElDescriptions', 'el-descriptions', 'ElDescriptionsItem', 'el-descriptions-item'],
    message: 'Use native dl/dt/dd with "@/styles/descriptions.css" instead.',
}];

export default defineConfig({
    ignores: [
        '**/node_modules/**', '**/dist/**', '**/dist-offline-analyzer/**', '**/dist-offline-minigame/**', '**/build/**', '**/public/**',
        '**/GuideView.vue',
    ],
}, {
    files: ['**/*.{js,ts,vue}'],
    plugins: {
        '@stylistic': stylistic,
        cypress: pluginCypress,
    },
    extends: [
        eslint.configs.recommended,
        importPlugin.flatConfigs.recommended,
        importPlugin.flatConfigs.typescript,
        tseslint.configs.all,
        ...pluginVue.configs['flat/recommended'],
        pluginCypress.configs.recommended,
        stylistic.configs.all,
        // ...vueI18n.configs.recommended, // 不兼容ts。https://github.com/intlify/eslint-plugin-vue-i18n/issues/32
    ],
    languageOptions: {
        globals: {
            ...globals.browser,
            ...pluginCypress.configs.recommended.globals,
        },
        parserOptions: {
            parser: tseslint.parser,
            projectService: {
                allowDefaultProject: [
                    'cypress.config.ts',
                    'eslint.config.js',
                ],
            },
            extraFileExtensions: ['.vue'],
        },
    },
    settings: {
        'vue-i18n': {
            localeDir: 'src/i18n/locales/*.ts',
            messageSyntaxVersion: '^11.0.0',
        },
        'import-x/resolver-next': [
            createTypeScriptImportResolver(),
        ],
    },
    rules: {
        'import-x/consistent-type-specifier-style': 'error',
        'import-x/dynamic-import-chunkname': 'off', // webpack项目用的，不适用vite
        'import-x/exports-last': 'off', // 和group-exports一致
        'import-x/extensions': ['error', { json: 'always' }],
        'import-x/first': 'error',
        'import-x/group-exports': 'off',
        'import-x/max-dependencies': 'off',
        'import-x/newline-after-import': 'error',
        'import-x/no-absolute-path': 'error',
        'import-x/no-anonymous-default-export': 'off',
        'import-x/no-cycle': 'error',
        'import-x/no-default-export': 'off',
        'import-x/no-deprecated': 'error',
        'import-x/no-duplicates': 'error',
        'import-x/no-dynamic-require': 'error',
        'import-x/no-empty-named-blocks': 'error',
        'import-x/no-extraneous-dependencies': ['error', {
            devDependencies: [
                '**/*.test.ts',
                '**/*.cy.ts',
                '**/cypress/**',
                'cypress.config.ts',
                'eslint.config.js',
                'vite.config.ts',
                'vite.offline.config.ts',
                'vite.minigame.config.ts',
                'scripts/offline-build.ts',
                'scripts/cdn-styles.ts',
            ],
            optionalDependencies: false,
            peerDependencies: false,
            includeTypes: true,
        }],
        'import-x/no-internal-modules': 'off',
        'import-x/no-mutable-exports': 'error',
        'import-x/no-named-default': 'error',
        'import-x/no-named-export': 'off',
        'import-x/no-namespace': 'error',
        'import-x/no-relative-packages': 'error',
        // 'import-x/no-relative-parent-imports', 'error',
        // 'import-x/no-rename-default': 'error',
        'import-x/no-restricted-paths': 'error',
        'import-x/no-self-import': 'error',
        'import-x/no-unassigned-import': 'off', // 和CSS导入冲突
        'import-x/no-unused-modules': 'off', // ESLint 10 removed the FileEnumerator API this rule relies on.
        'import-x/no-useless-path-segments': 'error',
        'import-x/no-webpack-loader-syntax': 'error',
        'import-x/order': [
            'error', {
                'newlines-between': 'always',
                alphabetize: {
                    order: 'asc',
                    caseInsensitive: true,
                },
                named: true,
            },
        ],
        'import-x/prefer-default-export': 'off',
        'import-x/prefer-namespace-import': 'error',

        'no-control-regex': 'off',
        'no-irregular-whitespace': 'off',
        'no-prototype-builtins': 'off',
        'vue/block-lang': ['error', { script: { lang: 'ts' } }],
        'vue/block-order': ['error', { order: ['template', 'script', 'style'] }],
        'vue/block-tag-newline': 'error',
        'vue/component-api-style': ['error', ['script-setup']],
        'vue/component-name-in-template-casing': 'error',
        'vue/component-options-name-casing': 'error',
        // 'vue/custom-event-name-casing': 'error',
        // 'vue/define-emits-declaration': 'error',
        'vue/define-macros-order': 'error',
        'vue/define-props-declaration': ['error', 'runtime'],
        'vue/define-props-destructuring': ['error', { destructure: 'never' }],
        // vue/enforce-style-attribute
        'vue/first-attribute-linebreak': 'error',
        'vue/html-closing-bracket-newline': 'error',
        'vue/html-closing-bracket-spacing': 'error',
        'vue/html-comment-content-newline': ['error', { multiline: 'never' }],
        'vue/html-comment-content-spacing': 'error',
        // 'vue/html-comment-indent': ['error', 4],
        'vue/html-indent': ['error', 4],
        'vue/html-quotes': ['error', 'double'],
        // vue/match-component-file-name
        // vue/match-component-import-name
        'vue/max-attributes-per-line': 'off', // 属性长度差别很大
        'vue/multi-word-component-names': 'off',
        'vue/no-duplicate-class-names': 'error',
        'vue/no-empty-component-block': 'error',
        'vue/no-import-compiler-macros': 'error',
        'vue/no-irregular-whitespace': ['error', { skipHTMLTextContents: true }],
        // vue/no-literals-in-template
        'vue/no-multiple-objects-in-class': 'error',
        // vue/no-negated-v-if-condition
        // vue/no-potential-component-option-typo
        // vue/no-ref-object-reactivity-loss
        // vue/no-restricted-block
        // vue/no-restricted-call-after-await
        // vue/no-restricted-class
        // vue/no-restricted-component-names
        // vue/no-restricted-component-options
        // vue/no-restricted-custom-event
        'vue/no-restricted-html-elements': ['error', ...restrictedHtmlElements],
        // vue/no-restricted-props
        // vue/no-restricted-static-attribute
        // vue/no-restricted-v-bind
        // vue/no-restricted-v-on
        // 'vue/no-root-v-if': 'error',
        // vue/no-setup-props-reactivity-loss
        // vue/no-static-inline-styles
        'vue/no-template-shadow': 'off',
        'vue/no-template-target-blank': 'error',
        // vue/no-this-in-before-route-enter
        'vue/no-undef-components': [
            'error', { ignorePatterns: [
                'ArrowLeft',
                'ArrowRight',
                'Check',
                'Ticket',
                'QuestionFilled',
                'router-view',
            ] },
        ],
        'vue/no-undef-directives': 'error',
        'vue/no-undef-properties': 'error',
        'vue/no-unsupported-features': ['error', { version: '^3.5.0' }],
        'vue/no-unused-emit-declarations': 'error',
        'vue/no-unused-properties': 'error',
        'vue/no-unused-refs': 'error',
        'vue/no-use-v-else-with-v-for': 'error',
        'vue/no-useless-mustaches': 'error',
        'vue/no-useless-v-bind': 'error',
        'vue/no-v-text': 'error',
        'vue/padding-line-between-blocks': 'error',
        'vue/padding-line-between-tags': 'off',
        // vue/padding-lines-in-component-definition
        'vue/prefer-define-options': 'error',
        'vue/prefer-prop-type-boolean-first': 'error',
        'vue/prefer-separate-static-class': 'error',
        'vue/prefer-single-event-payload': 'off',
        'vue/prefer-template': 'error',
        'vue/prefer-true-attribute-shorthand': 'error',
        'vue/prefer-use-template-ref': 'error',
        'vue/prefer-v-model': 'error',
        // vue/require-default-export
        // vue/require-direct-export
        // vue/require-emit-validator
        'vue/require-explicit-slots': 'error',
        'vue/require-expose': 'error',
        'vue/require-macro-variable-name': 'error',
        // vue/require-name-property
        'vue/require-prop-comment': 'off',
        'vue/require-typed-object-prop': 'error',
        'vue/require-typed-ref': 'error',
        'vue/require-v-for-key': 'off',
        'vue/restricted-component-names': 'off',
        'vue/singleline-html-element-content-newline': 'error',
        'vue/slot-name-casing': 'error',
        'vue/sort-keys': 'off',
        'vue/static-class-names-order': 'error',
        '@stylistic/array-bracket-newline': ['error', 'consistent'],
        '@stylistic/array-element-newline': 'off',
        '@stylistic/comma-dangle': ['error', 'always-multiline'],
        '@stylistic/function-call-argument-newline': ['error', 'consistent'],
        '@stylistic/function-paren-newline': ['error', 'consistent'],
        '@stylistic/indent-binary-ops': ['error', 4],
        '@stylistic/linebreak-style': 'off',
        '@stylistic/lines-around-comment': ['error', {
            beforeBlockComment: true,
            allowClassStart: true,
            allowInterfaceStart: true,
            allowTypeStart: true,
        }],
        '@stylistic/lines-between-class-members': ['error', {
            enforce: [
                { blankLine: 'never', prev: 'field', next: 'field' },
                { blankLine: 'always', prev: 'method', next: 'method' },
            ],
        }],
        '@stylistic/multiline-comment-style': 'off',
        '@stylistic/multiline-ternary': ['error', 'always-multiline'],
        '@stylistic/newline-per-chained-call': 'off',
        '@stylistic/no-extra-parens': ['error', 'all', {
            nestedBinaryExpressions: false,
            ignoredNodes: ['ArrowFunctionExpression[body.type=ConditionalExpression]'],
        }],
        '@stylistic/no-multiple-empty-lines': ['error', { max: 1 }],
        '@stylistic/object-curly-spacing': ['error', 'always'],
        '@stylistic/object-property-newline': ['error', { allowAllPropertiesOnSameLine: true }],
        '@stylistic/operator-linebreak': ['error', 'before'],
        '@stylistic/padded-blocks': ['error', 'never'],
        '@stylistic/quote-props': ['error', 'as-needed'],
        '@stylistic/quotes': ['error', 'single'],
        '@stylistic/space-before-function-paren': ['error', {
            anonymous: 'always',
            named: 'never',
        }],

        '@typescript-eslint/consistent-return': 'off', // 官方建议关闭
        '@typescript-eslint/explicit-function-return-type': 'off', // 和i18n冲突
        '@typescript-eslint/promise-function-async': 'off', // 和Vue Router、defineAsyncComponent冲突
        '@typescript-eslint/max-params': 'off',
        '@typescript-eslint/naming-convention': 'off', // TODO：涉及到前后端标准不一致的问题，很复杂
        '@typescript-eslint/no-redeclare': 'off',
        '@typescript-eslint/no-magic-numbers': 'off', // TODO
        '@typescript-eslint/no-unnecessary-condition': 'off', // false positive很多，参考https://typescript-eslint.io/rules/no-unnecessary-condition/#values-modified-within-function-calls
        '@typescript-eslint/no-unsafe-assignment': 'off', // 和defineAsyncComponent冲突
        '@typescript-eslint/no-unsafe-type-assertion': 'off', // 和Vue的PropType冲突
        '@typescript-eslint/no-use-before-define': 'off', // 为了代码可读性，有的函数需要放在最后
        '@typescript-eslint/prefer-enum-initializers': 'off',
        '@typescript-eslint/prefer-readonly-parameter-types': 'off',
        '@typescript-eslint/switch-exhaustiveness-check': ['error', {
            allowDefaultCaseForExhaustiveSwitch: false,
            considerDefaultExhaustiveForUnions: true,
        }],
        '@typescript-eslint/unified-signatures': 'off', // TODO
    },
}, {
    // Node's native config loader requires extensions in this TypeScript import chain.
    files: ['vite.config.ts', 'scripts/cdn-styles.ts'],
    rules: {
        'import-x/extensions': ['error', 'always', { ignorePackages: true }],
    },
}, {
    files: ['src/**/*.vue'],
    // Deferred components keep the existing layout, text and card restrictions.
    ignores: [
        'src/views/HomeView/NormalTournamentQueue.vue',
        'src/components/accountlinks/CardAdd.vue',
        'src/components/accountlinks/CardAddMineracer.vue',
        'src/components/accountlinks/CardBilibili.vue',
        'src/components/accountlinks/CardSaolei.vue',
        'src/components/accountlinks/CardWoM.vue',
        'src/components/accountlinks/CarouselControl.vue',
        'src/components/accountlinks/VideoImportQueue.vue',
    ],
    rules: {
        'vue/no-restricted-html-elements': [
            'error', ...restrictedHtmlElements, ...restrictedActionElements,
        ],
    },
}, {
    files: [
        'src/components/widgets/VideoAbstractDisplay.vue',
        'src/components/dialogs/ArbiterHelper.vue',
        'src/components/dialogs/MetasweeperHelper.vue',
        'src/components/dialogs/ViennaSweeperHelper.vue',
        'src/views/SettingView/Appearance.vue',
        'src/views/SettingView/App.vue',
        'src/views/VideoView.vue',
        'src/components/VideoUpload/Table.vue',
    ],
    rules: {
        'vue/no-restricted-html-elements': [
            'error', ...restrictedHtmlElements, ...restrictedActionElements, ...restrictedDescriptionsElements,
        ],
    },
}, {
    files: [
        'src/views/RankingView/SaoleiRanking.vue',
        'src/views/RankingView/PBRanking.vue',
        'src/components/Login/LoginForm.vue',
        'src/components/Login/RegisterForm.vue',
        'src/views/SettingView/App.vue',
        'src/components/VideoPlayer/NativePlayer.vue',
        'src/components/VideoPlayer/CustomCounterSettings.vue',
        'src/components/VideoPlayer/PlayerMainSettings.vue',
        'src/components/visualization/ColorSchemeSetting.vue',
        'src/components/VideoUpload/FileInputOptions.vue',
        'src/components/widgets/MultiSelector.vue',
        'src/components/Filters/SoftwareFilter.vue',
        'src/components/Filters/VideoStateFilter.vue',
        'src/components/Filters/MSLevelFilter.vue',
    ],
    rules: {
        'vue/no-restricted-html-elements': [
            'error', ...restrictedHtmlElements, ...restrictedActionElements, ...restrictedDescriptionsElements,
        ],
    },
}, {
    files: ['**/*.cy.ts'],
    rules: {
        // Cypress 组件测试中的 .vue 组件导入在 typescript-eslint 的 project service 中可能被解析为 error type，
        // 传给 cy.mount/helper 时会触发 no-unsafe-argument；这类报错不代表运行时参数不安全。
        '@typescript-eslint/no-unsafe-argument': 'off',
        '@typescript-eslint/no-unused-expressions': 'off',
    },
}, {
    // eslint无法正确判断Vue组件类型
    files: ['**/*.vue'],
    rules: {
        '@typescript-eslint/no-unsafe-call': 'off',
        '@typescript-eslint/no-unsafe-return': 'off',
        '@typescript-eslint/no-unsafe-member-access': 'off',
    },
});
