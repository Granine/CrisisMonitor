// app/feed/page.tsx
"use client"

import { RecentTweet, useRecentTweets } from "./api/api"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { AlertTriangle, CheckCircle, RefreshCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"


function FeedContent() {
  const { data, isLoading, refetch } = useRecentTweets()

  if (isLoading) {
    return (
      <main className="flex flex-col items-center justify-center min-h-screen p-10 text-muted-foreground">
        Loading recent tweets...
      </main>
    )
  }

  return (
    <main className="flex flex-col items-center gap-6 p-10">
      <p className="text-muted-foreground mb-4">
        Tweets classified within the last 30 minutes.
      </p>

      <div className="flex flex-col gap-4 w-full max-w-3xl">
        {data?.length ? (
          data.map((tweet: RecentTweet) => (
            <Card
              key={tweet.id}
              className={`border-2 ${
                tweet.is_real_disaster ? "border-red-400" : "border-green-400"
              }`}
            >
              <CardHeader className="flex items-center gap-2">
                {tweet.is_real_disaster ? (
                  <AlertTriangle className="text-red-500" />
                ) : (
                  <CheckCircle className="text-green-500" />
                )}
                <h2 className="text-lg font-semibold">
                  {tweet.is_real_disaster ? "🚨 Emergency Detected" : "✅ Safe"}
                </h2>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground italic">
                  {new Date(tweet.evaluated_at).toLocaleString()}
                </p>
                <p className="mt-2">{tweet.cleaned_tweet}</p>
              </CardContent>
            </Card>
          ))
        ) : (
          <p className="text-muted-foreground">No tweets found in the last 30 minutes.</p>
        )}
      </div>
    </main>
  )
}

const queryClient = new QueryClient()

export default function FeedPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <FeedContent />
    </QueryClientProvider>
  )
}
