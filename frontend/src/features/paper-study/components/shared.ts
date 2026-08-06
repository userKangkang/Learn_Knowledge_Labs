import type { PaperProblemCard, PaperProblemCardCreate } from "../../../entities/paper-study/types";

export type RunFn = (task: () => Promise<unknown>) => Promise<void>;
export type RefreshFn = () => Promise<void>;
export type SaveCardFn = (card: PaperProblemCard, patch: Partial<PaperProblemCard>) => Promise<void>;

export const overviewFields = [
  ["research_context", "研究场景"],
  ["core_problem", "核心问题"],
  ["main_approach", "主要方法"],
  ["claimed_effect", "论文报告的效果"],
] as const;

export const splitLines = (value: string) =>
  value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

export const emptyProblemCard = (): PaperProblemCardCreate => ({
  title: "",
  qualitative_overview: "",
  technical_interpretation: "",
  paper_claims: [],
  paper_not_said: [],
  verification_anchor: "",
  verification_prompt: "",
});
