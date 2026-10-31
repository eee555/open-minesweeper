export function getReplayPreviewUrl(id: number | string): string {
    return `${import.meta.env.VITE_BASE_API}/api/video/preview?id=${encodeURIComponent(id)}`;
}

export function getStrangeDustAnalyzerUrl(replayUrl: string): string {
    const url = new URL('https://strange-dust.github.io/minesweeper-replay-analyzer/');
    url.searchParams.set('replay', replayUrl);
    return url.href;
}
