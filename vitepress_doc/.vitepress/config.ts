import { defineConfig } from 'vitepress';
import type MarkdownIt from 'markdown-it';
import { graphvizMarkdownPlugin } from 'vitepress-plugin-graphviz';
import { getLocalizedPages } from './localized-pages';
import { isDocLocale, missingTitles } from './locales';

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
        const locale = pageData.relativePath.split('/')[0];
        if (isDocLocale(locale)) pageData.title = missingTitles[locale];
    },
    transformHead({ pageData, siteConfig }) {
        if (pageData.frontmatter.localeRedirect || !isDocLocale(pageData.relativePath.split('/')[0])) return;
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
                                { text: '纪念账号', link: '/zh/guide/memorial-accounts' },
                                { text: '作品页', link: '/zh/guide/works' },
                                { text: '扫雷软件', link: '/zh/guide/software' },
                                { text: '录像播放器', link: '/zh/guide/video-player' },
                                { text: '录像表达式参考', link: '/zh/guide/replay-expressions' },
                                { text: '扫雷标识', link: '/zh/guide/identifier' },
                                { text: '玩家认证', link: '/zh/guide/player-verification' },
                                { text: 'top 榜与 LSF 榜', link: '/zh/guide/top-lsf' },
                                { text: '勋章系统', link: '/zh/guide/medals' },
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
                                { text: '元扫雷使用教程', link: '/zh/guide/minesweeper/metasweeper' },
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
                                { text: '浏览器扩展', link: '/zh/guide/tools/browser-extension' },
                            ],
                        },
                    ],
                },
            },
        },
        es: {
            label: 'Español',
            lang: 'es',
            title: 'Guía de Open Minesweeper',
            description: 'Guía de usuario de Open Minesweeper',
            themeConfig: {
                outline: { label: 'En esta página' },
                docFooter: { prev: 'Página anterior', next: 'Página siguiente' },
                sidebarMenuLabel: 'Menú',
                returnToTopLabel: 'Volver arriba',
                darkModeSwitchLabel: 'Tema',
                lightModeSwitchTitle: 'Cambiar al tema claro',
                darkModeSwitchTitle: 'Cambiar al tema oscuro',
                langMenuLabel: 'Cambiar de idioma',
                skipToContentLabel: 'Saltar al contenido',
                editLink: {
                    pattern: 'https://github.com/eee555/saolei_website/edit/main/vitepress_doc/:path',
                    text: 'Editar esta página',
                },
                footer: {
                    copyright: '© 2023–2026 Open Minesweeper · openms.top',
                },
                lastUpdated: {
                    text: 'Última actualización',
                    formatOptions: {
                        dateStyle: 'medium',
                        timeStyle: 'short',
                        forceLocale: true,
                    },
                },
                nav: [
                    { text: 'Volver al sitio principal', link: mainSiteLink, target: '_self', rel: '' },
                ],
                sidebar: {
                    '/es/': [
                        {
                            text: 'Guía de usuario',
                            items: [
                                { text: 'Cuentas vinculadas', link: '/es/guide/account-links' },
                                { text: 'Cuentas conmemorativas', link: '/es/guide/memorial-accounts' },
                                { text: 'Obras de la comunidad', link: '/es/guide/works' },
                                { text: 'Programas de Buscaminas', link: '/es/guide/software' },
                                { text: 'Reproductor de repeticiones', link: '/es/guide/video-player' },
                                { text: 'Expresiones de repetición', link: '/es/guide/replay-expressions' },
                                { text: 'Identificadores de jugador', link: '/es/guide/identifier' },
                                { text: 'Verificación de jugadores', link: '/es/guide/player-verification' },
                                { text: 'Clasificaciones top y LSF', link: '/es/guide/top-lsf' },
                                { text: 'Medallas', link: '/es/guide/medals' },
                                { text: 'Minijuegos', link: '/es/guide/minigames' },
                                {
                                    text: 'Torneos',
                                    link: '/es/guide/tournament',
                                    items: [
                                        { text: 'Copa de la Oveja de Oro', link: '/es/guide/gsc' },
                                        { text: 'Torneo semanal', link: '/es/guide/weekly-tournament' },
                                    ],
                                },
                                { text: 'Cómo contribuir', link: '/es/guide/contribute' },
                                { text: 'Finanzas del sitio', link: '/es/guide/balance' },
                            ],
                        },
                        {
                            text: 'Tutoriales de Buscaminas',
                            items: [
                                { text: 'Controles y reglas', link: '/es/guide/minesweeper/mouse-event' },
                                { text: 'Guía de MetaSweeper', link: '/es/guide/minesweeper/metasweeper' },
                                { text: 'Glosario', link: '/es/guide/minesweeper/terminology' },
                                { text: 'Estadísticas', link: '/es/guide/minesweeper/stat' },
                                { text: 'Formato EVF', link: '/es/guide/minesweeper/evf-standard' },
                            ],
                        },
                        {
                            text: 'Desarrollo',
                            items: [
                                { text: 'Señales de Django', link: '/es/guide/development/signals' },
                                { text: 'Estructura de la caché', link: '/es/guide/development/cache' },
                                { text: 'Imágenes de las medallas', link: '/es/guide/development/medal-art' },
                                { text: 'Ajustes de las medallas', link: '/es/guide/development/medal-overrides' },
                                { text: 'Extracción de datos', link: '/es/guide/development/data-crawling' },
                                { text: 'Importación histórica de la GSC', link: '/es/guide/development/gsc-history-import' },
                                { text: 'Comandos de administración', link: '/es/guide/development/management-commands' },
                                { text: 'Formato de repetición de los minijuegos', link: '/es/guide/development/minigame-replay-format' },
                            ],
                        },
                        {
                            text: 'Herramientas',
                            items: [
                                { text: 'Yuanshen Toolbox', link: '/es/guide/tools/yuanshen-toolbox' },
                                { text: 'Extensión del navegador', link: '/es/guide/tools/browser-extension' },
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
                                { text: 'Memorial Accounts', link: '/en/guide/memorial-accounts' },
                                { text: 'Works', link: '/en/guide/works' },
                                { text: 'Minesweeper Software', link: '/en/guide/software' },
                                { text: 'Video Player', link: '/en/guide/video-player' },
                                { text: 'Replay Expressions', link: '/en/guide/replay-expressions' },
                                { text: 'Player Identifiers', link: '/en/guide/identifier' },
                                { text: 'Player Verification', link: '/en/guide/player-verification' },
                                { text: 'top and LSF Rankings', link: '/en/guide/top-lsf' },
                                { text: 'Medals', link: '/en/guide/medals' },
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
                                { text: 'MetaSweeper User Guide', link: '/en/guide/minesweeper/metasweeper' },
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
            options: {
                locales: {
                    es: { translations: {
                        button: { buttonText: 'Buscar', buttonAriaLabel: 'Buscar en la documentación' },
                        modal: {
                            displayDetails: 'Mostrar detalles', resetButtonTitle: 'Borrar búsqueda',
                            noResultsText: 'No se encontraron resultados para',
                            backButtonTitle: 'Cerrar búsqueda',
                            footer: { selectText: 'seleccionar', navigateText: 'navegar', closeText: 'cerrar' },
                        },
                    } },
                },
            },
        },
        socialLinks: [
            { icon: 'github', link: 'https://github.com/eee555/saolei_website' },
            { icon: 'gitee', link: 'https://gitee.com/ee55/saolei_website' },
            { icon: 'discord', link: 'https://discord.gg/ks8ngPX5bT' },
            { icon: 'qq', link: 'https://qm.qq.com/q/hNShGUQkJG' },
        ],
    },
});
