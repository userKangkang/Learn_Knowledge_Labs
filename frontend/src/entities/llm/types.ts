export type TextModelChoice = "deepseek-v4-pro" | "kimi-k2.6";

export interface LLMSettings {
  provider: string;
  model: string;
  search_model: string;
  kimi_model: string;
  base_url: string;
  moonshot_base_url: string;
  api_key_configured: boolean;
  kimi_api_key_configured: boolean;
  temperature: number;
  thinking_enabled: boolean;
  reasoning_effort: string;
  default_text_provider: string;
  supports_pdf_text_extract: boolean;
  supports_image_vision: boolean;
  web_search_uses_flash: boolean;
  multimodal_provider: string;
}
