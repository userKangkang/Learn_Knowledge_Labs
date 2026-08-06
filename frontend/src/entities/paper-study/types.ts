export type DocumentStatus = "UPLOADED" | "ANALYZING" | "READY" | "FAILED";
export type ConceptCategory = "MUST" | "ON_DEMAND" | "EXTENSION";
export type UnderstandingLevel = "NEEDS_WORK" | "BASIC" | "DEEP";
export type VerificationStatus = "PENDING" | "CAN_EXPLAIN" | "PARTLY" | "STILL_STUCK";

export interface PaperDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  source_text_char_count: number;
  kimi_detailed_analysis: string | null;
  error: string | null;
}

export interface PaperOverview {
  research_context: string;
  core_problem: string;
  main_approach: string;
  claimed_effect: string;
  user_understanding: string;
  user_status: "DRAFT" | "CONFIRMED" | "NEEDS_REVISION";
}

export interface PaperStudyMessage {
  id: string;
  study_id: string;
  stage: "OVERVIEW" | "PROBLEM_MAP";
  role: "USER" | "ASSISTANT";
  content: string;
  sequence_index: number;
  created_at: string;
}

export interface PaperProblemCard {
  id: string;
  study_id: string;
  title: string;
  qualitative_overview: string;
  technical_interpretation: string;
  paper_claims: string[];
  paper_not_said: string[];
  user_interest: string;
  user_stuck_point: string;
  selected: boolean;
  status: string;
  verification_anchor: string;
  verification_prompt: string;
  verification_answer: string;
  verification_status: VerificationStatus;
  order_index: number;
}

export interface PaperProblemCardCreate {
  title: string;
  qualitative_overview: string;
  technical_interpretation: string;
  paper_claims: string[];
  paper_not_said: string[];
  verification_anchor: string;
  verification_prompt: string;
}

export interface PaperConceptItem {
  id: string;
  title: string;
  explanation: string;
  category: ConceptCategory;
  paper_anchor: string;
  graph_node_id: string | null;
  user_status: UnderstandingLevel;
  order_index: number;
}

export interface PaperConceptRelation {
  id: string;
  source_item_id: string;
  target_item_id: string;
  relation_label: string;
}

export interface PaperConceptMap {
  id: string;
  problem_card_id: string;
  workflow_stage: "EMPTY" | "LANDSCAPE" | "REVIEW" | "COMPLETED";
  landscape_items: Array<Record<string, unknown>>;
  candidate_review: Array<Record<string, unknown>>;
  confirmed_candidate_keys: string[];
  items: PaperConceptItem[];
  relations: PaperConceptRelation[];
}

export interface PaperStudy {
  id: string;
  graph_id: string;
  title: string;
  status: string;
  document: PaperDocument | null;
  overview: PaperOverview;
  messages: PaperStudyMessage[];
  problem_cards: PaperProblemCard[];
  created_at: string;
  updated_at: string;
}
