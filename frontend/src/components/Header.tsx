import React, { useState, useEffect } from 'react';

interface HeaderProps {
  name: string;
  role: string;
  resumeConfigured: boolean;
  voiceEnabled: boolean;
}

export default function Header({
  name,
  role,
  resumeConfigured,
  voiceEnabled,
}: HeaderProps) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const stardate = now.getFullYear() + '.' + 
                      (now.getMonth() + 1).toString().padStart(2, '0') + '.' + 
                      now.getDate().toString().padStart(2, '0') + ' ' +
                      now.getHours().toString().padStart(2, '0') + ':' +
                      now.getMinutes().toString().padStart(2, '0') + ':' +
                      now.getSeconds().toString().padStart(2, '0');
      setTime(stardate);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

   return (
     <header className="border-b-2 border-neon-green/50 bg-gradient-to-r from-black/95 via-blue-950/20 to-black/95 px-4 sm:px-6 py-4 font-mono terminal-text relative overflow-hidden backdrop-blur-sm">
       {/* Decorative animated scanning lines */}
       <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-neon-green/30 to-transparent animate-pulse" />
       <div className="absolute top-2 left-0 w-full h-[1px] bg-neon-cyan/10 animate-scan" />
       
       <div className="flex items-center gap-4 sm:gap-6 flex-wrap relative z-10">
         <div className="relative group">
           <div className="w-12 h-12 sm:w-14 sm:h-14 border-2 border-neon-green bg-gradient-to-br from-black to-blue-950/40 flex items-center justify-center text-neon-green font-bold text-xl sm:text-2xl shadow-[0_0_20px_rgba(0,255,65,0.5)] group-hover:shadow-[0_0_35px_rgba(0,217,255,0.7)] transition-all duration-300 rounded-sm">
             [R]
           </div>
           <div className="absolute -top-1 -left-1 w-2 h-2 bg-neon-cyan animate-pulse" />
           <div className="absolute -bottom-1 -right-1 w-2 h-2 bg-neon-green animate-pulse" style={{ animationDelay: '0.5s' }} />
           <div className="absolute -inset-1 border border-neon-green/20 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity" />
         </div>

         <div className="min-w-0">
           <h1 className="text-xl sm:text-2xl font-bold text-neon-green tracking-tighter uppercase flex items-center gap-3 flex-wrap animate-pulse-glow">
             <span className="animate-bounce">🤖</span> RORI // COPILOT AI
           </h1>
           <p className="text-xs sm:text-sm text-neon-cyan/70 font-mono tracking-widest flex items-center gap-2 animate-pulse">
             <span className="w-2 h-2 bg-neon-green/60 rounded-full animate-pulse" />
             REPRESENTING {role} {name} • {time}
           </p>
         </div>

         <div className="ml-auto flex items-center gap-4 sm:gap-6 flex-wrap">
           <div className="flex flex-col items-end gap-1">
             <span className="text-[10px] text-neon-cyan/50 uppercase tracking-[0.2em] font-semibold">Data Link</span>
             <div className={`flex items-center gap-2 px-3 py-1 border-2 rounded backdrop-blur transition-all duration-300 ${resumeConfigured ? 'border-neon-green/60 bg-neon-green/10 text-neon-green shadow-[0_0_15px_rgba(0,255,65,0.2)]' : 'border-red-500/60 bg-red-500/10 text-red-500 shadow-[0_0_10px_rgba(255,0,0,0.1)]'} text-[10px] sm:text-xs font-bold tracking-widest`}>
               <span className={`w-2.5 h-2.5 rounded-full animate-pulse ${resumeConfigured ? 'bg-neon-green shadow-[0_0_10px_rgba(0,255,65,0.8)]' : 'bg-red-500 shadow-[0_0_8px_rgba(255,0,0,0.8)]'}`} />
               {resumeConfigured ? 'ONLINE' : 'OFFLINE'}
             </div>
           </div>

           <div className="flex flex-col items-end gap-1">
             <span className="text-[10px] text-neon-cyan/50 uppercase tracking-[0.2em] font-semibold">Voice Comms</span>
             <div className={`flex items-center gap-2 px-3 py-1 border-2 rounded backdrop-blur transition-all duration-300 ${voiceEnabled ? 'border-neon-green/60 bg-neon-green/10 text-neon-green shadow-[0_0_15px_rgba(0,255,65,0.2)]' : 'border-neon-green/30 bg-neon-green/5 text-neon-green/50'} text-[10px] sm:text-xs font-bold tracking-widest`}>
               <span className={`w-2.5 h-2.5 rounded-full ${voiceEnabled ? 'bg-neon-green shadow-[0_0_10px_rgba(0,255,65,0.8)]' : 'bg-neon-green/40'} ${voiceEnabled ? 'animate-pulse' : ''}`} />
               {voiceEnabled ? 'ACTIVE' : 'MUTED'}
             </div>
           </div>

           <div className="hidden md:flex flex-col items-end gap-1">
             <span className="text-[10px] text-neon-cyan/50 uppercase tracking-[0.2em] font-semibold">System State</span>
             <div className="flex items-center gap-2 px-3 py-1 border-2 border-neon-green/60 bg-neon-green/10 text-neon-green rounded text-[10px] sm:text-xs font-bold tracking-widest shadow-[0_0_15px_rgba(0,255,65,0.2)] transition-all hover:shadow-[0_0_25px_rgba(0,255,65,0.3)]">
               <span className="w-2.5 h-2.5 bg-neon-green shadow-[0_0_10px_rgba(0,255,65,0.8)] rounded-full animate-pulse" />
               OPTIMAL
             </div>
           </div>
         </div>
      </div>
    </header>
  );
}
