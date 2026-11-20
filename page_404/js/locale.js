let language = navigator.language;
try {
    language = JSON.parse(localStorage.getItem('local') || '{}').language || language;
} catch {
    // The standalone error page also works when site storage is unavailable.
}
if (typeof language === 'string' && /^es(?:-|$)/i.test(language)) {
    document.documentElement.lang = 'es';
    for (const element of document.querySelectorAll('[data-es]')) {
        element.textContent = element.dataset.es;
    }
}
