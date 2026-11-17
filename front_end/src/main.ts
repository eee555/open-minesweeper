function markOutdatedBrowser() {
    document.documentElement.classList.add('outdated-browser');
}

function errorText(error: unknown) {
    if (typeof error === 'string') return error;
    if (typeof error !== 'object' || error === null || !('message' in error)) return '';

    const { message } = error;
    const stack = 'stack' in error ? error.stack : '';
    const messageText = typeof message === 'string' ? message : '';
    const stackText = typeof stack === 'string' ? stack : '';
    return `${messageText}\n${stackText}`;
}

function isSupportedBrowser() {
    return typeof Array.prototype.toReversed === 'function'
        && typeof Promise.withResolvers === 'function'
        && typeof AbortSignal !== 'undefined'
        && typeof AbortSignal.any === 'function'
        && typeof AbortSignal.timeout === 'function';
}

function isUnsupportedBrowserError(error: unknown) {
    const text = errorText(error);
    if (!text.includes('is not a function')) return false;
    return text.includes('toReversed') || text.includes('withResolvers')
        || text.includes('AbortSignal.any') || text.includes('AbortSignal.timeout');
}

// 与 index.html 的提前检查保持一致；缺少依赖 API 时不加载应用，保留升级提示。
if (isSupportedBrowser()) {
    void import('./bootstrap').catch((error: unknown) => {
        if (isUnsupportedBrowserError(error)) markOutdatedBrowser();
        console.error(error);
    });
} else {
    markOutdatedBrowser();
}
