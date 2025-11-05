import { API_URL } from "@/utils/env"
import { useMutation, useQuery } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"

export type TweetInput = {
    text: string
}

export type PredictionOutput = {
    is_real_disaster: boolean
}

export function usePredictTweet() {
    return useMutation<PredictionOutput, AxiosError, TweetInput>({
        mutationKey: ["predict-tweet"],
        mutationFn: async (input: TweetInput) => {
            const response = await axios.post<PredictionOutput>(`${API_URL}/predict-tweet`, input)
            return response.data
        }
    })
}

export type RecentTweet = {
    "id": string,
    "cleaned_tweet": string,
    "is_real_disaster": boolean,
    "created_at": string
}

const mockData: RecentTweet[] = Array(5).fill(0).flatMap((_, idx) => ([{
    "id": String(2 * idx),
    "cleaned_tweet": "There's a huge fire downtown!",
    "is_real_disaster": true,
    "created_at": "2025-10-14T15:12:00Z"
},
{
    "id": String(2 * idx + 1),
    "cleaned_tweet": "David is in town",
    "is_real_disaster": false,
    "created_at": "2025-10-14T15:12:00Z"
}
]))

export function useRecentTweets() {
    return useQuery<RecentTweet[], AxiosError>({
        queryKey: ["recent-tweets"],
        queryFn: async () => {
            const now = new Date();
            const nowIsoUtc = now.toISOString();
            const yesterday = new Date(now);
            yesterday.setDate(now.getDate() - 1); // handles DST correctly
            const yesterdayIsoUtc = yesterday.toISOString();
              const res = await axios.get(`${API_URL}/events`, {
                params: {
                    start: yesterdayIsoUtc,
                    end: nowIsoUtc,
                    limit: 20
                }
              })
              return res.data
        },
        refetchInterval: 60000,
    })
}
