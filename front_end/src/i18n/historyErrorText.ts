import i18n from '@/i18n';
import { HistoryImportError } from '@/utils/historyImportError';

export function historyErrorText(error: unknown): string {
    if (error instanceof HistoryImportError) return i18n.global.t(`historyError.${error.code}`, error.params);
    return i18n.global.t('historyError.unknown');
}
