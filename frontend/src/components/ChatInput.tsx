'use client';

import React, { useEffect, useRef, useState } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t-2 border-neon-green/40 bg-gradient-to-b from-black/95 to-black/80 px-4 sm:px-6 py-4 sm:py-6 relative backdrop-blur-md"
    >
      {/* Decorative animated corners */}
      <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-neon-cyan/40 opacity-60" />
      <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-neon-green/40 opacity-60" />
      
      <div className="flex items-end gap-3 sm:gap-4 font-mono relative z-10">
        <div className="flex flex-col flex-1 gap-2">
          <label className="text-[10px] text-neon-cyan/60 uppercase tracking-[0.3em] ml-1 font-bold animate-pulse">▼ Input Command ▼</label>
          <div className="relative group">
            <span className="absolute left-3 top-3 text-neon-green select-none text-sm group-focus-within:animate-pulse group-focus-within:text-neon-cyan transition-colors">&gt;&gt;</span>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="INQUIRE ABOUT CAPTAIN SARTHAK OR BOOK AN INTERVIEW..."
              className="w-full resize-none bg-gradient-to-r from-black/70 to-blue-950/20 border border-neon-green/40 text-neon-green pl-8 pr-4 py-3 text-sm sm:text-base terminal-input focus:outline-none focus:border-neon-cyan focus:shadow-[0_0_20px_rgba(0,217,255,0.2)] placeholder:text-neon-green/30 uppercase min-h-[48px] transition-all duration-300 hover:border-neon-green/60 hover:bg-gradient-to-r hover:from-black/80 hover:to-blue-950/30 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
              rows={1}
              disabled={isLoading}
            />
            {/* Input border glow indicator */}
            <div className="absolute inset-0 rounded pointer-events-none bg-gradient-to-r from-neon-cyan/0 via-neon-green/10 to-neon-cyan/0 opacity-0 group-focus-within:opacity-100 transition-opacity duration-300" />
          </div>
        </div>
        
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="relative group overflow-hidden px-6 sm:px-8 py-3 bg-gradient-to-br from-neon-green/20 to-neon-green/5 border-2 border-neon-green/60 text-neon-green font-bold text-sm sm:text-base hover:from-neon-green/30 hover:to-neon-green/10 hover:border-neon-cyan hover:shadow-[0_0_25px_rgba(0,217,255,0.3)] disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-300 uppercase tracking-widest min-h-[48px] rounded hover:scale-105 active:scale-95"
        >
          {/* Animated glow beam behind button */}
          <div className="absolute -inset-1 bg-gradient-to-r from-neon-green/0 via-neon-green/30 to-neon-green/0 rounded opacity-0 group-hover:opacity-100 blur transition-opacity duration-300 -z-10" />
          
          {/* Inner shimmer effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
          
          <div className="relative flex items-center justify-center gap-2 sm:gap-3">
            {isLoading ? (
              <>
                <span className="w-2.5 h-2.5 bg-neon-green rounded-full animate-pulse" />
                <span className="text-neon-green animate-pulse font-semibold">TRANSMITTING</span>
              </>
            ) : (
              <>
                <span>⚡ EXECUTE</span>
              </>
            )}
          </div>
        </button>
      </div>
    </form>
  );
}
