import { create } from "zustand";

export type DialogTone = "default" | "danger";

export interface ConfirmDialogOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: DialogTone;
}

export interface PromptDialogOptions {
  title: string;
  description?: string;
  label?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
}

type DialogState =
  | {
      kind: "confirm";
      options: Required<
        Pick<ConfirmDialogOptions, "title" | "confirmLabel" | "cancelLabel" | "tone">
      > &
        Pick<ConfirmDialogOptions, "description">;
      resolve: (value: boolean) => void;
    }
  | {
      kind: "prompt";
      options: Required<
        Pick<
          PromptDialogOptions,
          "title" | "label" | "defaultValue" | "placeholder" | "confirmLabel" | "cancelLabel"
        >
      > &
        Pick<PromptDialogOptions, "description">;
      resolve: (value: string | null) => void;
    }
  | null;

interface DialogStore {
  dialog: DialogState;
  openConfirm: (options: ConfirmDialogOptions) => Promise<boolean>;
  openPrompt: (options: PromptDialogOptions) => Promise<string | null>;
  close: () => void;
}

export const useDialogStore = create<DialogStore>((set) => ({
  dialog: null,
  openConfirm: (options) =>
    new Promise<boolean>((resolve) => {
      set({
        dialog: {
          kind: "confirm",
          options: {
            title: options.title,
            description: options.description,
            confirmLabel: options.confirmLabel ?? "确认",
            cancelLabel: options.cancelLabel ?? "取消",
            tone: options.tone ?? "default",
          },
          resolve,
        },
      });
    }),
  openPrompt: (options) =>
    new Promise<string | null>((resolve) => {
      set({
        dialog: {
          kind: "prompt",
          options: {
            title: options.title,
            description: options.description,
            label: options.label ?? "内容",
            defaultValue: options.defaultValue ?? "",
            placeholder: options.placeholder ?? "",
            confirmLabel: options.confirmLabel ?? "确认",
            cancelLabel: options.cancelLabel ?? "取消",
          },
          resolve,
        },
      });
    }),
  close: () => set({ dialog: null }),
}));

export function confirmDialog(options: ConfirmDialogOptions): Promise<boolean> {
  return useDialogStore.getState().openConfirm(options);
}

export function promptDialog(options: PromptDialogOptions): Promise<string | null> {
  return useDialogStore.getState().openPrompt(options);
}
