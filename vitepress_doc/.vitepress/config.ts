import { defineConfig } from 'vitepress';
import type MarkdownIt from 'markdown-it';
import { graphvizMarkdownPlugin } from 'vitepress-plugin-graphviz';
import { getLocalizedPages } from './localized-pages';

const mainSiteLink = process.env.VITEPRESS_MAIN_SITE_URL
    ?? (process.env.NODE_ENV === 'development' ? 'http://localhost:8080/' : 'https://openms.top/');
const docsBase = process.env.VITEPRESS_BASE ?? '/docs/';
const localizedPages = getLocalizedPages();
const localizedUrls = new Set(Object.entries(localizedPages).flatMap(([locale, pages]) => pages.map((page) => `${locale}/${page}`)));

async function configureDiagramFences(md: MarkdownIt) {
    const defaultFence = md.renderer.rules.fence;

    md.renderer.rules.fence = (tokens, idx, options, env, self) => {
        const token = tokens[idx];
        const info = token.info.trim().split(/\s+/)[0];

        if (info === 'automaton' || info === 'mermaid') {
            return `<MermaidDiagram encoded-source="${encodeURIComponent(token.content)}" />`;
        }

        return defaultFence
            ? defaultFence(tokens, idx, options, env, self)
            : self.renderToken(tokens, idx, options);
    };

    await graphvizMarkdownPlugin(md, {
        processors: {
            neato: {
                preprocess: (content) => content,
            },
        },
    });
}

export default defineConfig({
    title: '开源扫雷网使用指南',
    description: '开源扫雷网用户指南',
    base: docsBase,
    srcExclude: ['README.md'],
    cleanUrls: true,
    lastUpdated: true,
    sitemap: {
        hostname: 'https://openms.top',
        outFilename: 'sitemap.xml',
        transformItems: (items) => items.filter((item) => localizedUrls.has(item.url)).map((item) => ({
            ...item,
            url: `${docsBase}${item.url}`,
            links: item.links?.filter((link) => localizedUrls.has(link.url)).map((link) => ({ ...link, url: `${docsBase}${link.url}` })),
        })),
    },
    head: [
        ['meta', { property: 'og:type', content: 'website' }],
        ['meta', { property: 'og:site_name', content: '开源扫雷网' }],
        ['meta', { name: 'robots', content: 'index, follow' }],
    ],
    transformPageData(pageData) {
        if (!pageData.frontmatter.localeRedirect) return;
        const locale = /^(zh|en)\//.exec(pageData.relativePath)?.[1];
        if (locale) pageData.title = locale === 'zh' ? '此页面暂无中文版本' : 'This page is not available in English';
    },
    transformHead({ pageData, siteConfig }) {
        if (pageData.frontmatter.localeRedirect || !/^(zh|en)\//.test(pageData.relativePath)) return;
        const path = pageData.relativePath.replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, '');
        const url = `https://openms.top${siteConfig.site.base}${path}`;
        return [['link', { rel: 'canonical', href: url }], ['meta', { property: 'og:url', content: url }]];
    },
    markdown: {
        config: configureDiagramFences,
    },
    locales: {
        zh: {
            label: '简体中文',
            lang: 'zh-CN',
            title: '开源扫雷网使用指南',
            description: '开源扫雷网用户指南',
            themeConfig: {
                editLink: {
                    pattern: 'https://github.com/eee555/saolei_website/edit/main/vitepress_doc/:path',
                    text: '编辑本页',
                },
                footer: {
                    copyright: '版权所有 @ 2023-2026 开源扫雷网 openms.top',
                },
                lastUpdated: {
                    text: '最后更新',
                    formatOptions: {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                        forceLocale: true,
                    },
                },
                nav: [
                    { text: '返回主站', link: mainSiteLink, target: '_self', rel: '' },
                ],
                sidebar: {
                    '/zh/': [
                        {
                            text: '使用指南',
                            items: [
                                { text: '账号关联', link: '/zh/guide/account-links' },
                                { text: '扫雷软件', link: '/zh/guide/software' },
                                { text: '录像播放器', link: '/zh/guide/video-player' },
                                { text: '录像表达式参考', link: '/zh/guide/replay-expressions' },
                                { text: '扫雷标识', link: '/zh/guide/identifier' },
                                { text: 'top 榜与 LSF 榜', link: '/zh/guide/top-lsf' },
                                { text: '小游戏', link: '/zh/guide/minigames' },
                                {
                                    text: '比赛功能',
                                    link: '/zh/guide/tournament',
                                    items: [
                                        { text: '金羊杯', link: '/zh/guide/gsc' },
                                        { text: '打卡赛', link: '/zh/guide/weekly-tournament' },
                                    ],
                                },
                                { text: '参与贡献', link: '/zh/guide/contribute' },
                                { text: '网站收支', link: '/zh/guide/balance' },
                            ],
                        },
                        {
                            text: '扫雷教程',
                            items: [
                                { text: '操作方式和规则', link: '/zh/guide/minesweeper/mouse-event' },
                                { text: '术语', link: '/zh/guide/minesweeper/terminology' },
                                { text: '数据', link: '/zh/guide/minesweeper/stat' },
                                { text: 'evf 标准', link: '/zh/guide/minesweeper/evf-standard' },
                            ],
                        },
                        {
                            text: '开发文档',
                            items: [
                                { text: '信号触发关系', link: '/zh/guide/development/signals' },
                                { text: '缓存结构', link: '/zh/guide/development/cache' },
                                { text: '勋章图片', link: '/zh/guide/development/medal-art' },
                                { text: '数据爬取指南', link: '/zh/guide/development/data-crawling' },
                                { text: 'GSC 历史录像补录', link: '/zh/guide/development/gsc-history-import' },
                                { text: '后端管理命令', link: '/zh/guide/development/management-commands' },
                                { text: '小游戏回放格式', link: '/zh/guide/development/minigame-replay-format' },
                            ],
                        },
                        {
                            text: '周边工具',
                            items: [
                                { text: '元神工具箱', link: '/zh/guide/tools/yuanshen-toolbox' },
                            ],
                        },
                    ],
                },
            },
        },
        en: {
            label: 'English',
            lang: 'en-US',
            title: 'Open Minesweeper Guide',
            description: 'Open Minesweeper user guide',
            themeConfig: {
                editLink: {
                    pattern: 'https://github.com/eee555/saolei_website/edit/main/vitepress_doc/:path',
                },
                footer: {
                    copyright: 'Copyright @ 2023-2026 Open Minesweeper openms.top',
                },
                lastUpdated: {
                    text: 'Last updated',
                    formatOptions: {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                        forceLocale: true,
                    },
                },
                nav: [
                    { text: 'Main Site', link: mainSiteLink, target: '_self', rel: '' },
                ],
                sidebar: {
                    '/en/': [
                        {
                            text: 'User Guide',
                            items: [
                                { text: 'Account Links', link: '/en/guide/account-links' },
                                { text: 'Minesweeper Software', link: '/en/guide/software' },
                                { text: 'Video Player', link: '/en/guide/video-player' },
                                { text: 'Replay Expressions', link: '/en/guide/replay-expressions' },
                                { text: 'Player Identifiers', link: '/en/guide/identifier' },
                                { text: 'top and LSF Rankings', link: '/en/guide/top-lsf' },
                                { text: 'Minigames', link: '/en/guide/minigames' },
                                {
                                    text: 'Tournaments',
                                    link: '/en/guide/tournament',
                                    items: [
                                        { text: 'Golden Sheep Cup', link: '/en/guide/gsc' },
                                        { text: 'Weekly Tournament', link: '/en/guide/weekly-tournament' },
                                    ],
                                },
                                { text: 'Contributing', link: '/en/guide/contribute' },
                                { text: 'Website Finances', link: '/en/guide/balance' },
                            ],
                        },
                        {
                            text: 'Minesweeper Tutorials',
                            items: [
                                { text: 'Controls and Rules', link: '/en/guide/minesweeper/mouse-event' },
                                { text: 'Terminology', link: '/en/guide/minesweeper/terminology' },
                                { text: 'Data', link: '/en/guide/minesweeper/stat' },
                                { text: 'evf Format', link: '/en/guide/minesweeper/evf-standard' },
                            ],
                        },
                        {
                            text: 'Development',
                            items: [
                                { text: 'Minigame Replay Format', link: '/en/guide/development/minigame-replay-format' },
                            ],
                        },
                    ],
                },
            },
        },
    },
    themeConfig: {
        localizedPages,
        logo: '/logo.png',
        search: {
            provider: 'local',
        },
        socialLinks: [
            { icon: 'github', link: 'https://github.com/eee555/saolei_website' },
            { icon: 'gitee', link: 'https://gitee.com/ee55/saolei_website' },
            { icon: 'discord', link: 'https://discord.gg/ks8ngPX5bT' },
            { icon: 'qq', link: 'https://qm.qq.com/q/hNShGUQkJG' },
        ],
    },
});
