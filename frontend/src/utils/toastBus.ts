import type { ToastArgs } from '@/components/BaseToast.vue'

type ShowFn = (args: ToastArgs) => void

let _show: ShowFn | null = null

/**
 * Register the global toast function.
 * Must be called once from App.vue after the BaseToast ref is ready.
 */
export function registerToast(fn: ShowFn): void {
  _show = fn
}

/**
 * Trigger the global toast from anywhere outside the Vue component tree
 * (e.g. Axios interceptors).
 */
export function showGlobalToast(args: ToastArgs): void {
  _show?.(args)
}
