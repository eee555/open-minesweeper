import { qqLoginEs } from '../qqLogin';

export default {
    local: 'es',
    name: 'Español',
    qqLogin: qqLoginEs,
    errorMsg: {
        import: {
            task_failed: 'La tarea de sincronización en segundo plano falló. Inténtalo de nuevo más tarde.',
        },
        accountlink: {
            title: 'Cuenta vinculada',
            not_found: 'La cuenta vinculada ya no existe. Actualiza la página.',
        },
    },
};
