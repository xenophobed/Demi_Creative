import apiClient from '@/api/client'

interface KidsDailyEmailSubscriptionResponse {
  email: string
  subscribed_at: string
  message: string
}

export const emailSubscriptionService = {
  async subscribeKidsDaily(email: string): Promise<KidsDailyEmailSubscriptionResponse> {
    const response = await apiClient.post<KidsDailyEmailSubscriptionResponse>(
      '/email-subscriptions/kids-daily',
      { email },
    )
    return response.data
  },
}
