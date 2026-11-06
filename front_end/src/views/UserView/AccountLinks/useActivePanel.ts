import { onBeforeUnmount, onDeactivated } from 'vue';

export function useActivePanel(): () => boolean {
    let active = true;
    const deactivate = () => {
        active = false;
    };
    onBeforeUnmount(deactivate);
    onDeactivated(deactivate);
    return () => active;
}
