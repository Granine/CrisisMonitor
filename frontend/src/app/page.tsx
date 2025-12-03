"use client"

import { useState, useEffect } from "react"
import { useMutation, useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import axios, { AxiosError } from "axios"
import { 
  AlertTriangle, 
  CheckCircle, 
  RefreshCcw, 
  Sparkles, 
  TrendingUp, 
  Clock, 
  Filter,
  Search,
  BarChart3,
  Shield,
  Zap
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardHeader, CardContent } from "@/components/ui/card"

// ============================================================================
// API CONFIGURATION
// ============================================================================
const API_URL = process.env.NEXT_PUBLIC_API_URL

// ============================================================================
// TYPES
// ============================================================================
type TweetInput = {
  text: string
}

type PredictionOutput = {
  is_real_disaster: boolean
}

type RecentTweet = {
  id: string
  cleaned_tweet: string
  is_real_disaster: boolean
  evaluated_at: string
}

// ============================================================================
// API HOOKS
// ============================================================================
function usePredictTweet(onSettled: () => void) {
  return useMutation<PredictionOutput, AxiosError, TweetInput>({
    mutationKey: ["predict-tweet"],
    mutationFn: async (input: TweetInput) => {
      const response = await axios.post<PredictionOutput>(`${API_URL}/predict-tweet`, input)
      return response.data
    },
    onSettled: async () => {
      // Wait for DB to save the new data
      await new Promise((res) => setTimeout(() => {res(0)}, 500))
      onSettled()
    }
  })
}

function useRecentTweets(timeRange: TimeRange) {
  return useQuery<RecentTweet[], AxiosError>({
    queryKey: ["recent-tweets", timeRange],
    queryFn: async () => {
      const now = new Date()
      const nowIsoUtc = now.toISOString()
      const startDate = new Date(now)
      
      // Calculate start time based on selected range
      switch (timeRange) {
        case "30min":
          startDate.setMinutes(now.getMinutes() - 30)
          break
        case "6hr":
          startDate.setHours(now.getHours() - 6)
          break
        case "1day":
          startDate.setDate(now.getDate() - 1)
          break
        case "10day":
          startDate.setDate(now.getDate() - 10)
          break
        case "30day":
          startDate.setDate(now.getDate() - 30)
          break
      }
      
      const startIsoUtc = startDate.toISOString()
      const res = await axios.get(`${API_URL}/events`, {
        params: {
          start: startIsoUtc,
          end: nowIsoUtc,
          limit: 100
        }
      })
      return res.data
    },
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  })
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================
type TimeRange = "30min" | "6hr" | "1day" | "10day" | "30day"

function CombinedDashboard() {
  const [tweet, setTweet] = useState("")
  const [filter, setFilter] = useState<"all" | "emergency" | "safe">("all")
  const [searchTerm, setSearchTerm] = useState("")
  const [timeRange, setTimeRange] = useState<TimeRange>("1day")
  const { data: recentTweets, isLoading, refetch } = useRecentTweets(timeRange)
  const { mutate, data: predictionData, isPending, reset } = usePredictTweet(refetch)

  // Calculate statistics
  const stats = {
    total: recentTweets?.length || 0,
    emergencies: recentTweets?.filter(t => t.is_real_disaster).length || 0,
    safe: recentTweets?.filter(t => !t.is_real_disaster).length || 0,
  }

  // Filter tweets
  const filteredTweets = recentTweets?.filter(tweet => {
    const matchesFilter = 
      filter === "all" || 
      (filter === "emergency" && tweet.is_real_disaster) ||
      (filter === "safe" && !tweet.is_real_disaster)
    const matchesSearch = tweet.cleaned_tweet.toLowerCase().includes(searchTerm.toLowerCase())
    return matchesFilter && matchesSearch
  })

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      {/* Fixed Header Section */}
      <div className="sticky top-0 z-50 bg-white/95 backdrop-blur-md shadow-lg border-b-2 border-blue-100">
        {/* Hero Section with Gradient */}
        <div className="relative overflow-hidden bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white py-8 px-6">
          <div className="absolute inset-0 bg-grid-white/[0.05] bg-[size:32px_32px]" />
          <div className="relative max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <Shield className="h-8 w-8" />
                  <h1 className="text-3xl font-bold">#Hurricane</h1>
                </div>
                <p className="text-sm text-blue-100">
                  Real-time emergency detection powered by advanced machine learning
                </p>
              </div>
              {/* Quick Stats in Header */}
              <div className="hidden md:flex items-center gap-6 text-white">
                <div className="text-center">
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-xs text-blue-100">Total</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-300">{stats.emergencies}</p>
                  <p className="text-xs text-blue-100">Emergencies</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-300">{stats.safe}</p>
                  <p className="text-xs text-blue-100">Safe</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Analyzer Section - Always Visible */}
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Tweet Input */}
            <div className="lg:col-span-2 space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-5 w-5 text-blue-600" />
                <h2 className="text-lg font-bold">AI Tweet Analyzer</h2>
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                  NLP Powered
                </span>
              </div>
              
              <div className="flex gap-3">
                <Textarea
                  value={tweet}
                  onChange={(e) => {setTweet(e.target.value); reset();}}
                  placeholder="e.g., 'Building on fire at Main Street, people evacuating...'"
                  className="flex-1 min-h-[80px] resize-none border-2 focus:border-blue-500 transition-colors"
                  maxLength={280}
                />
                <Button 
                  onClick={() => mutate({ text: tweet })} 
                  className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 px-8 shadow-lg"
                  disabled={!tweet.trim() || isPending}
                >
                  {isPending ? (
                    <>
                      <RefreshCcw className="h-5 w-5 animate-spin" />
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-5 w-5" />
                    </>
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground text-right">
                {tweet.length}/280 characters
              </p>
            </div>

            {/* Result Display */}
            <div className="lg:col-span-1 pt-8">
              {predictionData ? (
                <div className={`p-4 rounded-lg border-2 ${
                  predictionData.is_real_disaster 
                    ? "bg-red-50 border-red-300" 
                    : "bg-green-50 border-green-300"
                }`}>
                  <div className="flex items-center gap-3">
                    {predictionData.is_real_disaster ? (
                      <div className="p-2 bg-red-100 rounded-full">
                        <AlertTriangle className="h-6 w-6 text-red-600" />
                      </div>
                    ) : (
                      <div className="p-2 bg-green-100 rounded-full">
                        <CheckCircle className="h-6 w-6 text-green-600" />
                      </div>
                    )}
                    <div className="flex-1">
                      <h3 className={`text-lg font-bold ${
                        predictionData.is_real_disaster ? "text-red-700" : "text-green-700"
                      }`}>
                        {predictionData.is_real_disaster ? "⚠️ Emergency" : "✓ Safe"}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {predictionData.is_real_disaster
                          ? "Potential crisis detected"
                          : "No threats identified"}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50">
                  <div className="flex items-center gap-3">
                    <Zap className="h-6 w-6 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-600">Ready to analyze</p>
                      <p className="text-xs text-gray-500">Enter a tweet above</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Live Feed Section */}
        <Card className="bg-white/90 backdrop-blur-sm border-2 shadow-xl">
          <CardHeader className="bg-gradient-to-r pt-4 from-indigo-500 to-purple-500 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <div className="absolute inset-0 bg-white rounded-full animate-ping opacity-75" />
                  <div className="relative h-3 w-3 bg-white rounded-full" />
                </div>
                <h2 className="text-2xl font-bold">Live Feed Monitor</h2>
              </div>
              <Button 
                variant="secondary" 
                size="sm" 
                onClick={() => refetch()}
                disabled={isLoading}
                className="bg-white/20 hover:bg-white/30 text-white border-white/30"
              >
                <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
            <p className="text-indigo-100 pb-2 text-sm mt-2">
              Real-time classified tweets • Auto-refresh: 60s
            </p>
          </CardHeader>
          
          <CardContent className="pt-6 space-y-4">
            {/* Time Range Selector */}
            <div className="flex flex-wrap gap-2 pb-4 border-b border-gray-200">
              <span className="text-sm font-medium text-gray-700 flex items-center mr-2">
                <Clock className="h-4 w-4 mr-1" />
                Time Range:
              </span>
              <Button
                variant={timeRange === "30min" ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange("30min")}
                className="text-xs"
              >
                30 Minutes
              </Button>
              <Button
                variant={timeRange === "6hr" ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange("6hr")}
                className="text-xs"
              >
                6 Hours
              </Button>
              <Button
                variant={timeRange === "1day" ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange("1day")}
                className="text-xs"
              >
                1 Day
              </Button>
              <Button
                variant={timeRange === "10day" ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange("10day")}
                className="text-xs"
              >
                10 Days
              </Button>
              <Button
                variant={timeRange === "30day" ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange("30day")}
                className="text-xs"
              >
                30 Days
              </Button>
            </div>

            {/* Search and Filter */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search tweets..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border-2 rounded-md focus:outline-none focus:border-blue-500 transition-colors"
                />
              </div>
              
              <div className="flex gap-2">
                <Button
                  variant={filter === "all" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter("all")}
                  className="flex-1 sm:flex-none"
                >
                  <Filter className="mr-2 h-4 w-4" />
                  All ({stats.total})
                </Button>
                <Button
                  variant={filter === "emergency" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter("emergency")}
                  className="flex-1 sm:flex-none border-red-300 text-red-600 hover:bg-red-50"
                >
                  <AlertTriangle className="mr-2 h-4 w-4" />
                  Emergencies ({stats.emergencies})
                </Button>
                <Button
                  variant={filter === "safe" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFilter("safe")}
                  className="flex-1 sm:flex-none border-green-300 text-green-600 hover:bg-green-50"
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Safe ({stats.safe})
                </Button>
              </div>
            </div>

            {/* Tweets List */}
            <div className="space-y-3">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <RefreshCcw className="h-8 w-8 animate-spin mb-3" />
                  <p>Loading recent tweets...</p>
                </div>
              ) : filteredTweets?.length ? (
                filteredTweets.map((tweet: RecentTweet, index: number) => (
                  <Card
                    key={tweet.id}
                    className={`border-l-4 hover:shadow-md transition-all duration-200 animate-in fade-in slide-in-from-bottom ${
                      tweet.is_real_disaster 
                        ? "border-l-red-500 bg-red-50/50 hover:bg-red-50" 
                        : "border-l-green-500 bg-green-50/50 hover:bg-green-50"
                    }`}
                    style={{ animationDelay: `${index * 50}ms` }}
                  >
                    <CardContent className="pt-4 pb-4">
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-full ${
                          tweet.is_real_disaster ? "bg-red-100" : "bg-green-100"
                        }`}>
                          {tweet.is_real_disaster ? (
                            <AlertTriangle className="h-5 w-5 text-red-600" />
                          ) : (
                            <CheckCircle className="h-5 w-5 text-green-600" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                              tweet.is_real_disaster 
                                ? "bg-red-200 text-red-800" 
                                : "bg-green-200 text-green-800"
                            }`}>
                              {tweet.is_real_disaster ? "EMERGENCY" : "SAFE"}
                            </span>
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(tweet.evaluated_at).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed">{tweet.cleaned_tweet}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Search className="h-12 w-12 mb-3 opacity-50" />
                  <p className="text-center">
                    {searchTerm ? "No tweets match your search." : "No tweets found in the last 30 days."}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

// ============================================================================
// EXPORT WITH QUERY CLIENT PROVIDER
// ============================================================================
const queryClient = new QueryClient()

export default function Page() {
  return (
    <QueryClientProvider client={queryClient}>
      <CombinedDashboard />
    </QueryClientProvider>
  )
}
