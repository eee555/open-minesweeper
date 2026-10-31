import { videoplayerstore } from '@/store';
import { getReplayPreviewUrl } from '@/utils/replayLinks';

export function preview(id: number | undefined | null): void {
    if (id === undefined || id === null || id <= 0) return;
    videoplayerstore.id = id;
    videoplayerstore.url = getReplayPreviewUrl(id);
    videoplayerstore.visible = true;
}
