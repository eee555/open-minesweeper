type HistoryImportErrorCode = 'invalidField' | 'size' | 'headers' | 'columns' | 'duplicate' | 'empty' | 'malformedCsv' | 'uploadTime' | 'duration' | 'range';

export class HistoryImportError extends Error {
    public readonly code: HistoryImportErrorCode;
    public readonly params: Record<string, string | number>;

    public constructor(code: HistoryImportErrorCode, message: string, params: Record<string, string | number> = {}) {
        super(message);
        this.name = 'HistoryImportError';
        this.code = code;
        this.params = params;
    }
}
