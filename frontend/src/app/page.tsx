"use client"
// app/page.tsx
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { useState } from "react"
import { AlertTriangle, CheckCircle } from "lucide-react"

export default function Home() {
  const [tweet, setTweet] = useState("")
  const [result, setResult] = useState<"emergency" | "safe" | null>(null)

  const handleCheck = async () => {
    // Fake classify
    if (tweet.toLowerCase().includes("help")) {
      setResult("emergency")
    } else {
      setResult("safe")
    }
  }

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

      <Button onClick={handleCheck} className="w-40">Check Emergency</Button>

      {result && (
        <Card className={`max-w-md mt-6 border-2 ${result === "emergency" ? "border-red-400" : "border-green-400"}`}>
          <CardHeader className="flex items-center gap-2">
            {result === "emergency" ? (
              <AlertTriangle className="text-red-500" />
            ) : (
              <CheckCircle className="text-green-500" />
            )}
            <h2 className="text-xl font-semibold">
              {result === "emergency" ? "🚨 Emergency Detected" : "✅ Safe"}
            </h2>
          </CardHeader>
          <CardContent>
            {result === "emergency"
              ? "This tweet looks like it might describe an emergency situation."
              : "This tweet does not appear to be an emergency."}
          </CardContent>
        </Card>
      )}
    </main>
  )
}
