export type ProblemLinkType = "CORE" | "TOUCHED";

export interface SharedProblem {
  id: string;
  graph_id: string;
  title: string;
  description: string;
  created_at: string;
  updated_at: string;
  coverage_paper_count: number;
  coverage_core_count: number;
  coverage_touched_count: number;
}

export interface SharedProblemEdge {
  id: string;
  graph_id: string;
  source_problem_id: string;
  target_problem_id: string;
  relation_label: string;
  created_at: string;
}

export interface ProblemCardLink {
  id: string;
  graph_id: string;
  problem_card_id: string;
  shared_problem_id: string;
  link_type: ProblemLinkType;
  created_at: string;
}

export interface ProblemMapPaperCard {
  id: string;
  title: string;
  qualitative_overview: string;
  selected: boolean;
}

export interface ProblemMapPaper {
  study_id: string;
  title: string;
  research_context: string;
  core_problem: string;
  main_approach: string;
  cards: ProblemMapPaperCard[];
}

export interface RelatedPaperSearchTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ProblemMapPosition {
  id: string;
  graph_id: string;
  entity_type: "PAPER" | "CARD" | "PROBLEM";
  entity_id: string;
  position_x: number;
  position_y: number;
}

export interface ProblemMapBundle {
  problems: SharedProblem[];
  edges: SharedProblemEdge[];
  links: ProblemCardLink[];
  papers: ProblemMapPaper[];
  positions: ProblemMapPosition[];
}

export interface ProblemMapSuggestionProblem {
  key: string;
  title: string;
  description: string;
  parent_key: string | null;
}

export interface ProblemMapSuggestionEdge {
  source_ref: string;
  target_ref: string;
  relation_label: string;
}

export interface ProblemMapSuggestionCardLink {
  problem_card_id: string;
  problem_ref: string;
  link_type: ProblemLinkType;
}

export interface ProblemMapSuggestResponse {
  problems: ProblemMapSuggestionProblem[];
  edges: ProblemMapSuggestionEdge[];
  card_links: ProblemMapSuggestionCardLink[];
  note: string;
}

export interface ProblemMapApplyRequest {
  problems: Array<{ key: string; title: string; description: string }>;
  edges: Array<{ source_ref: string; target_ref: string; relation_label: string }>;
  card_links: Array<{ problem_card_id: string; problem_ref: string; link_type: ProblemLinkType }>;
}

export interface ProblemMapApplyResult {
  created_problems: number;
  created_edges: number;
  created_links: number;
}
