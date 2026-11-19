import { videoNumericParamKeys } from './types';
import type { VideoNumericParamKey } from './types';

import type { AnyVideo } from '@/utils/fileIO';

const pluckKeys = new Set<VideoNumericParamKey>(['pluck', 'luck', 'expected_bbbv_solved_per_attempt', 'expected_bbbv_solved_per_win', 'expected_time_per_attempt', 'expected_time_per_win']);
const analysedVideos = new WeakSet<AnyVideo>();

export function createEvaluationContext(video: AnyVideo): Record<string, number> {
    const values: Record<string, number> = {};
    for (const key of videoNumericParamKeys) {
        Object.defineProperty(values, key, {
            enumerable: true,
            get: () => {
                if (pluckKeys.has(key) && !analysedVideos.has(video)) {
                    video.analyse_for_features(['pluck']);
                    analysedVideos.add(video);
                }
                return video[key];
            },
        });
    }
    return values;
}
