export interface CdnStyle {
    id: string;
    cdn: string;
    local: string;
    font?: string;
}

declare global {
    interface Window {
        __cdnStylesReady?: Promise<void>;
    }
}

// This function is also compiled into a small, classic inline script in production HTML.
// Start before the app module downloads, without making the HTML loader wait for CSS.
export function loadCdnStyles(styles: CdnStyle[], cdnTimeout = 4000, localTimeout = 15000): Promise<void> {
    const anchor = document.head.querySelector('style, link[rel="stylesheet"]') ?? document.currentScript;
    const completed = new Set<string>();
    const total = styles.reduce((count, style) => count + (style.font !== undefined && style.font !== '' ? 2 : 1), 0);
    const states = new Map(styles.map((style) => [style.id, 'cdn']));
    let fallbackReason = '';

    function updateStatus() {
        const values = [...states.values()];
        let zh = '正在从 CDN 加载';
        let en = 'Loading from CDN';
        let es = 'Cargando desde la CDN';
        if (values.includes('failed')) {
            zh = '加载失败，请刷新重试';
            es = 'Error de carga. Actualiza la página para reintentar';
            en = 'Loading failed. Please refresh to retry';
        } else if (values.includes('local')) {
            zh = `CDN ${fallbackReason === 'timeout' ? '加载较慢' : '不可用'}，正在从本站加载`;
            es = fallbackReason === 'timeout' ? 'La CDN tarda en responder. Cargando desde este sitio' : 'La CDN no está disponible. Cargando desde este sitio';
            en = `CDN ${fallbackReason === 'timeout' ? 'is slow' : 'unavailable'}. Loading from this site`;
        } else if (completed.size === total) {
            zh = '已就绪，正在准备页面';
            en = 'Ready. Preparing page';
            es = 'Listo. Preparando la página';
        }
        const label = document.querySelector<HTMLElement>('#startup-loading-resource-status');
        const chinese = label?.querySelector('[lang="zh-CN"]');
        const english = label?.querySelector('[lang="en"]');
        if (chinese) chinese.textContent = `界面资源 ${completed.size}/${total}：${zh}`;
        if (english) english.textContent = `Interface resources ${completed.size}/${total}: ${en}`;
        const spanish = label?.querySelector('[lang="es"]');
        if (spanish) spanish.textContent = `Recursos de la interfaz ${completed.size}/${total}: ${es}`;
        if (label) label.hidden = false;
        const progress = document.querySelector<HTMLProgressElement>('#startup-loading progress');
        if (progress) {
            progress.max = total;
            progress.value = completed.size;
            progress.setAttribute('aria-describedby', 'startup-loading-label startup-loading-resource-status');
        }
    }

    // Cached responses may finish before the parser reaches the HTML placeholder.
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', updateStatus, { once: true });
    updateStatus();
    const ready = Promise.all(styles.map((style) => new Promise<void>((resolve, reject) => {
        let active: HTMLLinkElement | undefined;
        let timer: ReturnType<typeof setTimeout>;
        let settled = false;

        function finish(error?: Error) {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            if (active) {
                active.onload = null;
                active.onerror = null;
            }
            states.set(style.id, error ? 'failed' : 'ready');
            updateStatus();
            if (error) reject(error);
            else resolve();
        }

        function start(local: boolean) {
            const previous = active;
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = local ? style.local : style.cdn;
            link.dataset.cdnStyle = style.id;
            link.dataset.source = local ? 'local' : 'cdn';
            active = link;
            states.set(style.id, local ? 'local' : 'cdn');
            updateStatus();

            function failed(reason = 'error') {
                if (settled || active !== link) return;
                if (local) finish(new Error(`Failed to load stylesheet: ${style.id}`));
                else {
                    fallbackReason = reason;
                    start(true);
                }
            }

            link.onerror = () => {
                failed();
            };
            link.onload = () => {
                if (settled || active !== link) return;
                completed.add(`${style.id}/css`);
                updateStatus();
                if (style.font === undefined || style.font === '') {
                    finish();
                    return;
                }
                // A stylesheet can succeed while its cross-origin icon font fails.
                void document.fonts.load(style.font, '\ue900').then((faces) => {
                    if (settled || active !== link) return;
                    if (faces.length > 0) {
                        completed.add(`${style.id}/font`);
                        finish();
                    } else failed();
                }, () => {
                    failed();
                });
            };
            clearTimeout(timer);
            timer = setTimeout(() => {
                failed('timeout');
            }, local ? localTimeout : cdnTimeout);
            // Replace in place so a late fallback stays before the site's overrides.
            document.head.insertBefore(link, previous ?? anchor);
            previous?.remove();
        }

        start(false);
    }))).then(() => undefined);

    // The app module may still be downloading when both sources fail.
    // Keep the rejection for bootstrap's error UI without an unhandled rejection.
    void ready.catch(() => undefined);
    return ready;
}
