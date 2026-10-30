import type { MS_Software } from './ms_const';
import { getSoftwareExtension } from './strings';

export function getReplayDownloadUrl(id: number | string): string {
    return `${import.meta.env.VITE_BASE_API}/api/video/download/${encodeURIComponent(id)}`;
}

export function getReplayPreviewUrl(id: number | string, software: MS_Software): string {
    return `${import.meta.env.VITE_BASE_API}/api/video/preview?id=${encodeURIComponent(id + getSoftwareExtension(software))}`;
}

export function getStrangeDustAnalyzerUrl(replayUrl: string): string {
    const url = new URL('https://strange-dust.github.io/minesweeper-replay-analyzer/');
    url.searchParams.set('replay', replayUrl);
    return url.href;
}
