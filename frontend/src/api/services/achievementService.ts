import apiClient from "../client";
import type { AchievementListResponse } from "@/types/api";

const ACHIEVEMENT_BASE = "/achievements";

export const achievementService = {
  async getForChild(childId: string): Promise<AchievementListResponse> {
    const response = await apiClient.get<AchievementListResponse>(
      `${ACHIEVEMENT_BASE}/${encodeURIComponent(childId)}`,
    );
    return response.data;
  },
};
