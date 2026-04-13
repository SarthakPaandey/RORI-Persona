import React from 'react';

export default function TypingIndicator() {
   return (
     <div className="flex justify-start message-enter font-mono">
       <div className="bg-gradient-to-br from-black/90 to-purple-950/30 border-2 border-neon-green/60 px-3 sm:px-4 py-2 sm:py-3 shadow-[0_0_20px_rgba(0,255,65,0.2)] ml-2 sm:ml-8 rounded-lg backdrop-blur-sm hover:shadow-[0_0_30px_rgba(0,217,255,0.3)] transition-all">
         <div className="text-xs text-neon-green/60 mb-1 sm:mb-2 border-b border-neon-green/30 pb-1 flex justify-between uppercase text-[10px] sm:text-xs font-bold">
           <span className="animate-pulse">🤖 RORI // SHIP AI</span>
           <span className="text-neon-cyan/70 animate-pulse">●</span>
         </div>
         <div className="flex items-center mt-2 sm:mt-3 opacity-90 h-6 sm:h-7 gap-2">
           <span className="text-neon-green text-sm sm:text-base leading-none uppercase tracking-widest font-bold animate-pulse-glow">⚙ PROCESSING</span>
           <div className="flex gap-1">
             <span className="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-bounce" style={{ animationDelay: '0s' }} />
             <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
             <span className="w-1.5 h-1.5 bg-neon-cyan rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
           </div>
         </div>
       </div>
     </div>
   );
}
