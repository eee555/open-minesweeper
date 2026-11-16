export class ScreenWakeLock {
    private sentinel: WakeLockSentinel | null = null;
    private active = false;
    private acquiring = false;

    private readonly handleVisibilityChange = () => {
        if (this.active && document.visibilityState === 'visible') {
            void this.acquire();
        }
    };

    private readonly handleRelease = () => {
        this.sentinel = null;
        if (this.active && document.visibilityState === 'visible') {
            void this.acquire();
        }
    };

    async acquire(): Promise<void> {
        if (!navigator.wakeLock || !this.active || this.acquiring || this.sentinel !== null) return;
        this.acquiring = true;
        try {
            const sentinel = await navigator.wakeLock.request('screen');
            if (!this.active) {
                void sentinel.release();
                return;
            }
            this.sentinel = sentinel;
            sentinel.addEventListener('release', this.handleRelease, { once: true });
        } catch {
            // Browsers may deny the request, e.g. low battery or hidden document.
        } finally {
            this.acquiring = false;
        }
    }

    request(): void {
        if (this.active) return;
        this.active = true;
        document.addEventListener('visibilitychange', this.handleVisibilityChange);
        void this.acquire();
    }

    release(): void {
        this.active = false;
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
        const sentinel = this.sentinel;
        this.sentinel = null;
        void sentinel?.release();
    }
}
