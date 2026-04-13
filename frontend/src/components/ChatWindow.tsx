"use client";

import React, { useEffect, useRef } from "react";

import { Message } from "@/lib/types";

import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";

interface ChatWindowProps {
  readonly messages: Message[];
  readonly isLoading: boolean;
}

export default function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastMessage = messages.at(-1);
  const showTypingIndicator =
    isLoading
    && (lastMessage?.role !== 'assistant' || !lastMessage?.content?.trim());

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-4 sm:space-y-6 bg-gradient-to-b from-black via-black to-blue-950/20 relative">
      {/* Animated background elements */}
      <div className="fixed inset-0 pointer-events-none opacity-30">
        <div className="absolute top-20 left-10 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-20 right-10 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }} />
      </div>
      
      <div className="relative z-10">
        <div className="text-center text-xs text-neon-green/60 font-mono mb-4 sm:mb-8 py-2 sm:py-3 border-y border-neon-green/30 text-[10px] sm:text-xs backdrop-blur-sm">
          <span className="inline-block animate-pulse">[</span>
          <span className="animate-pulse-glow">ENCRYPTED CHANNEL SECURED</span>
          <span className="animate-pulse"> / </span>
          <span className="text-neon-cyan animate-pulse-glow">STARDATE 2026.04.13</span>
          <span className="animate-pulse">]</span>
        </div>
      </div>
      
      <div className="relative z-10 space-y-4 sm:space-y-6">{messages.map((message) => {
        const isTypingPlaceholder =
          isLoading &&
          message.id === lastMessage?.id &&
          message.role === "assistant" &&
          !message.content?.trim();
        
        if (isTypingPlaceholder) return null;

        return <MessageBubble key={message.id} message={message} />;
      })}

      {showTypingIndicator && <TypingIndicator />}

      <div ref={bottomRef} className="h-4" /></div>
    </div>
  );
}
