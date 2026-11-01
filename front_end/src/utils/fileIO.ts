import { AvfVideo, EvfVideo, MvfVideo, RmvVideo } from 'ms-toollib';

import { CustomLevel } from './customlevel';
import { arbiterTimeStampToDate, generalTimeStampToDate } from './datetime';
import type { MS_Level, MS_Mode } from './ms_const';
import { VideoAbstract } from './videoabstract';

export type AnyVideo = AvfVideo | EvfVideo | RmvVideo | MvfVideo;

export function get_software(video: AnyVideo): 'e' | 'a' | 'r' | 'm' {
    if (video instanceof AvfVideo) return 'a';
    else if (video instanceof EvfVideo) return 'e';
    else if (video instanceof RmvVideo) return 'r';
    else return 'm';
}

export function load_video_file(buffer: ArrayBuffer, filename: string): AnyVideo {
    const u8 = new Uint8Array(buffer);
    const ext = filename.slice(-3);

    let video: AnyVideo;
    if (ext === 'avf') {
        video = new AvfVideo(u8, filename);
    } else if (ext === 'evf') {
        video = new EvfVideo(u8, filename);
    } else if (ext === 'rmv') {
        video = new RmvVideo(u8, filename);
    } else if (ext === 'mvf') {
        video = new MvfVideo(u8, filename);
    } else {
        throw new Error('Unsupported file extension');
    }
    video.parse();
    video.analyse();
    // video.analyse_for_features(['pluck']);
    return video;
}

export function extract_stat(video: AnyVideo): VideoAbstract {
    video.current_time = 1e8;
    return new VideoAbstract({
        id: 0,
        level: get_video_level(video),
        mode: String(video.mode).padStart(2, '0') as MS_Mode,
        software: get_software(video),
        timems: video.rtime_ms,
        bv: video.bbbv_solved,
        ce: video.ce,
        right_ce: video.rce,
        cl: video.cl,
        path: video.path,
        end_time: video instanceof AvfVideo ? arbiterTimeStampToDate(video.end_time) : generalTimeStampToDate(video.end_time),
    });
}

export function get_video_level(video: AnyVideo): MS_Level | CustomLevel {
    if (video.level === 6) {
        return new CustomLevel(video.row, video.column, video.mine_num);
    }
    return ['b', 'i', 'e'][video.level - 3] as MS_Level;
}

export function downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    try {
        a.click();
    } finally {
        a.remove();
        URL.revokeObjectURL(url);
    }
}

export async function fileHash(buffer: ArrayBuffer): Promise<string> {
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export interface DirectoryNewFileEvent {
    file: File;
    handle: FileSystemFileHandle;
    directory: FileSystemDirectoryHandle;
}

export type DirectoryNewFileListener = (event: DirectoryNewFileEvent) => void | Promise<void>;

export interface DirectoryNewFileEmitterOptions {
    pollIntervalMs?: number;
    emitExisting?: boolean;
}

export interface DirectoryNewFileEmitter {
    readonly running: boolean;
    start: (emitExisting?: boolean, pollIntervalMs?: number) => Promise<void>;
    stop: () => void;
    scan: () => Promise<DirectoryNewFileEvent[]>;
    onFile: (listener: DirectoryNewFileListener) => () => void;
}

class PollingDirectoryNewFileEmitter implements DirectoryNewFileEmitter {
    private readonly directory: FileSystemDirectoryHandle;
    private readonly knownFiles = new Set<string>();
    private readonly listeners = new Set<DirectoryNewFileListener>();
    private readonly pollIntervalMs: number;
    private readonly emitExisting: boolean;
    private timer: ReturnType<typeof setInterval> | undefined;
    private activeScan?: Promise<DirectoryNewFileEvent[]>;
    private generation = 0;
    private starting = false;

    public constructor(directory: FileSystemDirectoryHandle, options: DirectoryNewFileEmitterOptions = {}) {
        this.directory = directory;
        this.pollIntervalMs = options.pollIntervalMs ?? 1000;
        this.emitExisting = options.emitExisting ?? false;
    }

    public get running() {
        return this.starting || this.timer !== undefined;
    }

    public async start(emitExisting = this.emitExisting, pollIntervalMs = this.pollIntervalMs) {
        if (this.running) return;
        const generation = ++this.generation;
        this.starting = true;
        try {
            await this.activeScan;
            if (generation !== this.generation) return;
            if (emitExisting) await this.scan();
            else await this.rememberCurrentFiles(generation);
            if (generation !== this.generation) return;
            this.timer = setInterval(() => {
                void this.scan().catch(console.error);
            }, pollIntervalMs);
        } finally {
            if (generation === this.generation) this.starting = false;
        }
    }

    public stop() {
        this.generation += 1;
        this.starting = false;
        clearInterval(this.timer);
        this.timer = undefined;
    }

    public async scan() {
        if (this.activeScan) return this.activeScan;
        this.activeScan = this.scanFiles(this.generation);
        try {
            return await this.activeScan;
        } finally {
            this.activeScan = undefined;
        }
    }

    public onFile(listener: DirectoryNewFileListener) {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    }

    private async scanFiles(generation: number) {
        const events: DirectoryNewFileEvent[] = [];
        for await (const handle of this.directory.values()) {
            if (generation !== this.generation) break;
            if (handle.kind !== 'file' || this.knownFiles.has(handle.name)) continue;
            const file = await handle.getFile();
            if (generation !== this.generation) break;
            this.knownFiles.add(handle.name);
            const event = { file, handle, directory: this.directory };
            events.push(event);
            // Apply backpressure so cancelling a scan leaves unprocessed files for resume.
            for (const listener of this.listeners) {
                if (generation !== this.generation) break;
                try {
                    await listener(event);
                } catch (error) {
                    console.error(error);
                }
            }
        }
        return events;
    }

    private async rememberCurrentFiles(generation: number) {
        for await (const handle of this.directory.values()) {
            if (generation !== this.generation) break;
            if (handle.kind === 'file') {
                this.knownFiles.add(handle.name);
            }
        }
    }
}

export function createDirectoryNewFileEmitter(directory: FileSystemDirectoryHandle, options: DirectoryNewFileEmitterOptions = {}): DirectoryNewFileEmitter {
    return new PollingDirectoryNewFileEmitter(directory, options);
}
