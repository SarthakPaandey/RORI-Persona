"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

import { Message } from "@/lib/types";

import CalendarWidget from "./CalendarWidget";
import SourceCitation from "./SourceCitation";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === "user";

   return (
     <div
       className={`flex message-enter font-mono ${isUser ? "justify-end" : "justify-start"}`}
     >
       <div
         className={`max-w-[90%] sm:max-w-[85%] px-3 sm:px-4 py-2 sm:py-3 relative rounded-lg border backdrop-blur-sm transition-all duration-300 hover:scale-[1.02] ${
           isUser
             ? "bg-gradient-to-br from-black/80 to-blue-950/40 text-neon-green border-neon-green/50 ml-2 sm:ml-8 hover:border-neon-green/80 hover:shadow-[0_0_20px_rgba(0,255,65,0.2)]"
             : "bg-gradient-to-br from-black/90 to-purple-950/30 text-neon-green border-neon-green/60 mr-2 sm:mr-8 shadow-[0_0_15px_rgba(0,255,65,0.15)] hover:border-neon-cyan/60 hover:shadow-[0_0_25px_rgba(0,217,255,0.25)]"
         }`}
       >
         {/* Animated border glow */}
         {!isUser && (
           <div className="absolute -inset-0.5 bg-gradient-to-r from-neon-cyan/0 via-neon-green/10 to-neon-cyan/0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 animate-glow-border pointer-events-none" />
         )}
         
         <div className="relative z-10">
           <div className="text-xs text-neon-green/60 mb-1 border-b border-neon-green/30 pb-1.5 uppercase flex flex-row justify-between items-center tracking-widest text-[10px] sm:text-xs font-bold">
             <span className="animate-pulse">
               {isUser ? "👤 GUEST // RECRUITER" : "🤖 RORI // SHIP AI"}
             </span>
             <span className="text-neon-cyan/70 text-[9px] animate-pulse">●</span>
           </div>
           <div
             className={`chat-markdown terminal-text text-sm sm:text-base overflow-wrap break-words space-y-2 leading-relaxed`}
           >
             <ReactMarkdown>{message.content}</ReactMarkdown>
           </div>

          {(message.bookingLink || (message.availableSlots?.length ?? 0) > 0) && (
            <div className="mt-4 border-t border-neon-green/30 pt-4">
              <CalendarWidget
                slots={message.availableSlots}
                bookingLink={message.bookingLink}
                timezone={message.timezone}
              />
            </div>
          )}

          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="mt-4 border-t border-neon-green/20 pt-3">
              <button
                type="button"
                onClick={() => setShowSources(!showSources)}
                className="text-xs text-neon-green/70 hover:text-neon-cyan transition-all duration-200 hover:bg-neon-green/10 px-2 py-1.5 uppercase font-semibold rounded border border-neon-green/30 hover:border-neon-cyan/50"
              >
                {showSources ? "◀ HIDE" : "▶ EXAMINE"} SECURE SOURCES ({message.sources.length})
              </button>

              {showSources && (
                <div className="mt-3 space-y-2 border-l-2 border-neon-green/40 pl-3 animate-pulse-glow">
                  {message.sources.map((source, idx) => (
                    <SourceCitation key={idx} source={source} />
                  ))}
                </div>
              )}
            </div>
          )}
         </div>
      </div>
    </div>
  );
}
