import apiClient from "../client";

export interface TranscriptionResponse {
  text: string;
  language: string;
  duration_ms: number;
  safety_passed: boolean;
}

export interface TranscribePayload {
  audio: Blob;
  filename: string;
  targetAge: number;
  languageHint?: string;
}

export const transcriptionService = {
  async transcribe(payload: TranscribePayload): Promise<TranscriptionResponse> {
    const form = new FormData();
    form.append("audio", payload.audio, payload.filename);
    form.append("target_age", String(payload.targetAge));
    if (payload.languageHint) {
      form.append("language_hint", payload.languageHint);
    }
    const response = await apiClient.post<TranscriptionResponse>(
      "/audio/transcriptions",
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },
};
