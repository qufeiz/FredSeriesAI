"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarContent, AvatarFallback } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, User, Send, Loader2, AlertCircle } from "lucide-react";

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  error?: boolean;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: "Hello! I'm EconoGraph, your Federal Reserve Economic Data assistant. I can help you understand economic trends, analyze FRED data, and answer questions about monetary policy. What would you like to explore today?",
      role: 'assistant',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // TODO: Replace with actual API call to your LangGraph backend
      // const response = await fetch('https://my-langgraph-app.fly.dev/threads', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({
      //     message: input,
      //     user_id: 'demo_user',
      //     thread_id: 'main_thread'
      //   })
      // });

      // Simulate API response for now
      await new Promise(resolve => setTimeout(resolve, 2000));

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: `I received your question: "${input}". This is a demo response. In the full version, I would analyze FRED economic data and provide insights about your query using my knowledge of Federal Reserve data, economic indicators, and monetary policy.

Here are some key points I would typically cover:
• Current economic indicators and trends
• Historical data context and comparisons
• Federal Reserve policy implications
• Data visualization and charts

Would you like me to elaborate on any specific aspect?`,
        role: 'assistant',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: "I'm sorry, I encountered an error processing your request. Please try again or check if the backend service is running.",
        role: 'assistant',
        timestamp: new Date(),
        error: true,
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSampleQuestion = (question: string) => {
    setInput(question);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Messages */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex items-start space-x-3 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <Avatar className="w-8 h-8">
                  <AvatarFallback className={message.error ? 'bg-red-100' : 'bg-slate-100'}>
                    {message.error ? (
                      <AlertCircle className="w-4 h-4 text-red-600" />
                    ) : (
                      <Bot className="w-4 h-4 text-slate-600" />
                    )}
                  </AvatarFallback>
                </Avatar>
              )}

              <Card
                className={`max-w-xs sm:max-w-md lg:max-w-lg xl:max-w-xl p-3 ${
                  message.role === 'user'
                    ? 'bg-slate-900 text-white border-slate-800'
                    : message.error
                    ? 'bg-red-50 text-red-900 border-red-200'
                    : 'bg-white border-slate-200'
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {message.content}
                </p>
                <p className={`text-xs mt-2 ${
                  message.role === 'user' ? 'text-slate-300' : 'text-slate-500'
                }`}>
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </Card>

              {message.role === 'user' && (
                <Avatar className="w-8 h-8">
                  <AvatarFallback className="bg-slate-900">
                    <User className="w-4 h-4 text-white" />
                  </AvatarFallback>
                </Avatar>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex items-start space-x-3">
              <Avatar className="w-8 h-8">
                <AvatarFallback className="bg-slate-100">
                  <Bot className="w-4 h-4 text-slate-600" />
                </AvatarFallback>
              </Avatar>
              <Card className="bg-white border-slate-200 p-3">
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin text-slate-600" />
                  <span className="text-sm text-slate-600">Analyzing economic data...</span>
                </div>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-4 bg-white flex-shrink-0">
        <div className="flex items-end space-x-3">
          <div className="flex-1">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about economic trends, FRED data, or monetary policy..."
              className="resize-none min-h-[48px] max-h-32"
              disabled={isLoading}
            />
          </div>
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            size="icon"
            className="h-12 w-12"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </Button>
        </div>

        {/* Sample Questions */}
        <div className="mt-3">
          <p className="text-xs text-slate-500 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-1">
            {[
              "What's the current unemployment rate trend?",
              "Explain inflation and interest rates relationship",
              "Show me recent GDP growth data",
            ].map((question, index) => (
              <Button
                key={index}
                variant="outline"
                size="sm"
                onClick={() => handleSampleQuestion(question)}
                disabled={isLoading}
                className="text-xs h-7 px-2"
              >
                {question}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}