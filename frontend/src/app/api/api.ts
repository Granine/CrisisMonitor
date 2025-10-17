import { API_URL } from "@/utils/env"
import { useMutation, useQuery } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"

export type TweetInput = {
    tweet: string
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
    "tweet": string,
    "is_real_disaster": boolean,
    "created_at": string
}

const mockData: RecentTweet[] = Array(5).fill(0).flatMap((_, idx) => ([{
    "id": String(2 * idx),
    "tweet": "There's a huge fire downtown!",
    "is_real_disaster": true,
    "created_at": "2025-10-14T15:12:00Z"
},
{
    "id": String(2 * idx + 1),
    "tweet": "David is in town",
    "is_real_disaster": false,
    "created_at": "2025-10-14T15:12:00Z"
}
]))

export function useRecentTweets() {
    return useQuery<RecentTweet[], AxiosError>({
        queryKey: ["recent-tweets"],
        queryFn: async () => {
            return mockData
            //   const res = await axios.post(`${API_URL}/recent`)
            //   return res.data
        },
        refetchInterval: 60000,
    })
}
