"use client"
// app/page.tsx
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { useEffect, useState } from "react"
import { AlertTriangle, CheckCircle } from "lucide-react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { usePredictTweet } from "./api/api"

function Home() {
  const [tweet, setTweet] = useState("")
  const { mutate, data } = usePredictTweet()

  return (
    <main className="flex flex-col items-center gap-6 p-10">
      <h1 className="text-4xl font-bold">Is this tweet an emergency? 🐤</h1>
      <p className="text-muted-foreground">
        Paste a tweet below and let our AI detect emergencies in real time.
      </p>

      <Textarea
        value={tweet}
        onChange={(e) => setTweet(e.target.value)}
        placeholder="Paste tweet here..."
        className="max-w-xl"
      />

      <Button onClick={() => {
        mutate({ tweet })
      }} className="w-40">Check Emergency</Button>

      {data && (
        <Card className={`max-w-md mt-6 border-2 ${data.is_real_disaster ? "border-red-400" : "border-green-400"}`}>
          <CardHeader className="flex items-center gap-2">
            {data.is_real_disaster ? (
              <AlertTriangle className="text-red-500" />
            ) : (
              <CheckCircle className="text-green-500" />
            )}
            <h2 className="text-xl font-semibold">
              {data.is_real_disaster ? "🚨 Emergency Detected" : "✅ Safe"}
            </h2>
          </CardHeader>
          <CardContent>
            {data.is_real_disaster
              ? "This tweet looks like it might describe an emergency situation."
              : "This tweet does not appear to be an emergency."}
          </CardContent>
        </Card>
      )}
    </main>
  )
}


const queryClient = new QueryClient()

export default function HomeWithContext() {
  return (
    <QueryClientProvider client={queryClient}>
      <Home />
    </QueryClientProvider>
  )
}
