import type { Component } from 'vue';

export interface NavigationItem {
    id: string;
    label: string;
    icon?: string;
    // 需要复用同一实现与固定文案的第三方登录入口，渲染为菜单项内容。
    component?: Component;
    iconOnly?: boolean;
    primary?: boolean;
    to?: string;
    href?: string;
    target?: '_blank';
    action?: () => void | Promise<void>;
    children?: NavigationItem[];
    checked?: boolean;
    testId?: string;
}
