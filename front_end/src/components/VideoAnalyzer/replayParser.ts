import { AvfVideo, EvfVideo, MvfVideo, RmvVideo } from 'ms-toollib';

import type { MS_Software } from '@/utils/ms_const';

export type ReplayVideo = AvfVideo | EvfVideo | MvfVideo | RmvVideo;
export interface ReplaySource {
    data: ArrayBuffer;
    filename: string;
    software: MS_Software;
}

const parsers = { a: AvfVideo, e: EvfVideo, m: MvfVideo, r: RmvVideo, x: EvfVideo };

export function parseReplay(data: ArrayBuffer, filename: string, software: MS_Software, features: string[] = []): ReplayVideo {
    const video = new parsers[software](new Uint8Array(data), filename);
    try {
        video.parse();
        video.analyse();
        if (features.length > 0) video.analyse_for_features(features);
        return video;
    } catch (error) {
        video.free();
        throw error;
    }
}
