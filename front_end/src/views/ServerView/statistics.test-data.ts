import { memoryResponse } from './memory.test-data';
import type { MonitorSnapshot } from './statistics';

export function monitorResponse(): MonitorSnapshot {
    const sampledAt = '2026-10-25T12:00:00Z';
    return {
        diskusage: { sampled_at: sampledAt, total: 8192, used: 6144, free: 2048, video: 3072, db: 1024 },
        tasksummary: { sampled_at: sampledAt, total: 1000, status: { READY: 100, RUNNING: 100, SUCCESSFUL: 700, FAILED: 100 } },
        videosummary: { sampled_at: sampledAt, total: 1000, software: { a: 1000 }, level: { e: 1000 }, mode: { '00': 1000 }, state: { c: 1000 } },
        memoryusage: memoryResponse(),
    };
}
