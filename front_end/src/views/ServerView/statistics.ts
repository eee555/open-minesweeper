import type { MemoryUsageResponse } from './memory';

export const statisticsColors = ['#409eff', '#e6a23c', '#67c23a', '#f56c6c', '#a879e6', '#909399', '#22a6a1', '#c67c3b', '#ca6ca4', '#7086c1'];

export interface DiskUsage {
    sampled_at: string;
    total: number;
    used: number;
    free: number;
    video: number | null;
    db: number | null;
}

export interface TaskSummary {
    sampled_at: string;
    total: number;
    status: Record<'READY' | 'RUNNING' | 'SUCCESSFUL' | 'FAILED', number>;
}

export type VideoSummary = { sampled_at: string; total: number } & Record<'software' | 'level' | 'mode' | 'state', Record<string, number>>;

export interface MonitorSnapshot {
    diskusage: DiskUsage | null;
    tasksummary: TaskSummary | null;
    videosummary: VideoSummary | null;
    memoryusage: MemoryUsageResponse | null;
}
