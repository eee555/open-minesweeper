import { useLocalStorage } from '@vueuse/core';

import { defaultAnalyzerConfig } from '@/components/VideoAnalyzer/config';
import type { AnalyzerConfig } from '@/components/VideoAnalyzer/config';

export { defaultAnalyzerConfig, layouts } from '@/components/VideoAnalyzer/config';
export type { AnalyzerConfig, AnalyzerLayout, CellSizeMode, CursorShape } from '@/components/VideoAnalyzer/config';

// Keep the in-memory config authoritative; storage events would replace it whenever another tab clears or changes settings.
export const analyzerConfig = useLocalStorage<AnalyzerConfig>('video-analyzer-config', defaultAnalyzerConfig(), { mergeDefaults: true, listenToStorageChanges: false });
// Retain supported options while dropping obsolete export settings from saved configurations.
const savedVideoExport = analyzerConfig.value.videoExport;
analyzerConfig.value.videoExport = { format: savedVideoExport.format, fps: savedVideoExport.fps, quality: savedVideoExport.quality };
