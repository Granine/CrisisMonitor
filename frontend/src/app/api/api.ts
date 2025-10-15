import { API_URL } from "@/utils/env"
import { useMutation } from "@tanstack/react-query"
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