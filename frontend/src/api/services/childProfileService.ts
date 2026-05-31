import apiClient from "../client";
import type {
  ChildProfile,
  ChildProfileConsentUpdateRequest,
  ChildProfileCreateRequest,
  ChildProfileListResponse,
  ChildProfileUpdateRequest,
} from "@/types/api";

const CHILD_PROFILE_BASE = "/child-profiles";

export const childProfileService = {
  async list(): Promise<ChildProfileListResponse> {
    const response = await apiClient.get<ChildProfileListResponse>(
      CHILD_PROFILE_BASE,
    );
    return response.data;
  },

  async create(payload: ChildProfileCreateRequest): Promise<ChildProfile> {
    const response = await apiClient.post<ChildProfile>(
      CHILD_PROFILE_BASE,
      payload,
    );
    return response.data;
  },

  async update(
    childId: string,
    payload: ChildProfileUpdateRequest,
  ): Promise<ChildProfile> {
    const response = await apiClient.patch<ChildProfile>(
      `${CHILD_PROFILE_BASE}/${encodeURIComponent(childId)}`,
      payload,
    );
    return response.data;
  },

  async setDefault(childId: string): Promise<ChildProfile> {
    const response = await apiClient.post<ChildProfile>(
      `${CHILD_PROFILE_BASE}/${encodeURIComponent(childId)}/default`,
    );
    return response.data;
  },

  async archive(childId: string): Promise<ChildProfile> {
    const response = await apiClient.post<ChildProfile>(
      `${CHILD_PROFILE_BASE}/${encodeURIComponent(childId)}/archive`,
    );
    return response.data;
  },

  async updateConsent(
    childId: string,
    payload: ChildProfileConsentUpdateRequest,
  ): Promise<ChildProfile> {
    const response = await apiClient.patch<ChildProfile>(
      `${CHILD_PROFILE_BASE}/${encodeURIComponent(childId)}/consent`,
      payload,
    );
    return response.data;
  },
};
