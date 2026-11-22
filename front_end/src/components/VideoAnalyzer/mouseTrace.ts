import { defaultMouseTraceColor, defaultMouseTraceMarkers, mouseTraceMarkerActions } from '@putianyi888/vue3-minesweeper-board';
import type { MouseTraceColor, MouseTraceEvent, MouseTraceMarkerAction, MouseTraceMarkers, MouseTraceResolvedMarker } from '@putianyi888/vue3-minesweeper-board';

export interface ReplayMouseTraceEvent extends MouseTraceEvent {
    timeMs: number;
    eventIndex: number;
}

export interface MouseTraceAppearance {
    lineWidth: number;
    color: MouseTraceColor;
    markers: Record<MouseTraceMarkerAction, MouseTraceResolvedMarker & { enabled: boolean }>;
}

export function defaultMouseTraceAppearance(): MouseTraceAppearance {
    return {
        lineWidth: 0.08,
        color: { ...defaultMouseTraceColor },
        markers: Object.fromEntries(mouseTraceMarkerActions.map((action) => [action, { ...defaultMouseTraceMarkers[action], enabled: false }])) as MouseTraceAppearance['markers'],
    };
}

export function mouseTraceAppearanceProps(appearance: MouseTraceAppearance): { lineWidth: number; color: MouseTraceColor; markers: MouseTraceMarkers } {
    return {
        lineWidth: appearance.lineWidth,
        color: appearance.color,
        markers: Object.fromEntries(mouseTraceMarkerActions.map((action) => {
            const { enabled, ...marker } = appearance.markers[action];
            return [action, enabled ? marker : false];
        })),
    };
}

export { mouseTraceRange, readMouseTrace, readMouseTraceAsync } from './replayMouseTrace';

export function sliderToTailSeconds(value: number): number {
    return value === 1 ? Infinity : value / (1 - value);
}

export function tailSecondsToSlider(value: number): number {
    return value === Infinity ? 1 : value / (1 + value);
}
