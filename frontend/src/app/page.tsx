import { BarChart3, MessageSquare, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import ChatInterface from "@/components/chat-interface";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-10 h-10 bg-slate-900 rounded-xl">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">EconoGraph</h1>
                <p className="text-sm text-slate-600">Federal Reserve Economic Intelligence</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                AI Ready
              </Badge>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-12 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-3 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">About EconoGraph</CardTitle>
                <CardDescription>
                  Your AI-powered assistant for Federal Reserve Economic Data (FRED) analysis and insights.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center space-x-3">
                  <MessageSquare className="w-5 h-5 text-slate-600" />
                  <span className="text-sm">Natural language queries</span>
                </div>
                <div className="flex items-center space-x-3">
                  <TrendingUp className="w-5 h-5 text-slate-600" />
                  <span className="text-sm">Economic trend analysis</span>
                </div>
                <div className="flex items-center space-x-3">
                  <BarChart3 className="w-5 h-5 text-slate-600" />
                  <span className="text-sm">Data visualization</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-slate-700">Sample Questions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  "What's the current unemployment rate?",
                  "How has inflation changed recently?",
                  "Show me GDP growth trends",
                  "Compare interest rates over time"
                ].map((question, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    size="sm"
                    className="w-full justify-start text-left h-auto p-2 text-xs"
                  >
                    {question}
                  </Button>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Chat Interface */}
          <div className="lg:col-span-9">
            <Card className="h-[600px] flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <MessageSquare className="w-5 h-5" />
                  <span>Economic Chat</span>
                </CardTitle>
                <CardDescription>
                  Ask questions about economic data, trends, and Federal Reserve policies.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0 flex-1 min-h-0">
                <ChatInterface />
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white/50 mt-12">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <p>Powered by LangGraph & Federal Reserve Economic Data</p>
            <p>&copy; 2024 EconoGraph</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
