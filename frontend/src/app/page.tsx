"use client";

import { useEffect, useState } from "react";
import ChatInput from "@/components/ChatInput";
import ChatWindow from "@/components/ChatWindow";
import Header from "@/components/Header";
import { useChat } from "@/hooks/useChat";
import { usePersona } from "@/hooks/usePersona";

 const SpaceBackground = () => {
   const [stars, setStars] = useState<
     { id: number; left: string; top: string; delay: string; duration: string; size: number }[]
   >([]);
   const [isMobile, setIsMobile] = useState(false);

   useEffect(() => {
     // Detect mobile for performance optimization
     const checkMobile = typeof window !== 'undefined' && window.innerWidth < 768;
     setIsMobile(checkMobile);
     
     // Generate stars only on client side to avoid hydration mismatch
     const starCount = checkMobile ? 40 : 120;
     
     const generatedStars = Array.from({ length: starCount }).map((_, i) => ({
       id: i,
       // Stars start scattered across the screen
       left: `${Math.random() * 120}vw`,
       top: `${Math.random() * 100}vh`,
       // Randomise delay so stars don't all spawn at once
       delay: `${Math.random() * 10}s`,
       // Faster = closer (parallax). Range: 2s (close) to 12s (distant)
       duration: `${2 + Math.random() * 10}s`,
       // Bigger = closer (parallax)
       size: Math.random() * 2 + 1,
     }));
     setStars(generatedStars);
   }, []);

   return (
     <div className="space-background">
       {stars.map((star) => (
         <div
           key={star.id}
           className="star"
           style={{
             left: star.left,
             top: star.top,
             width: `${star.size}px`,
             height: `${star.size}px`,
             animationDelay: star.delay,
             animationDuration: star.duration,
           }}
         />
       ))}
       {/* Distant light dots generated above, adding shooting stars here - fewer on mobile */}
       {!isMobile && (
         <>
           <div
             className="shooting-star"
             style={{ top: "10vh", left: "80vw", animationDelay: "2s" }}
           />
           <div
             className="shooting-star"
             style={{ top: "40vh", left: "60vw", animationDelay: "7s" }}
           />
           <div
             className="shooting-star"
             style={{ top: "20vh", left: "30vw", animationDelay: "12s" }}
           />
           <div
             className="shooting-star"
             style={{ top: "60vh", left: "10vw", animationDelay: "18s" }}
           />
         </>
       )}

       {/* Multiple UFOs with varying sizes, speeds, and timing */}
       <div
         className="absolute text-4xl sm:text-6xl drop-shadow-[0_0_20px_rgba(0,255,255,0.8)] opacity-0 will-change-transform"
         style={{ animation: "ship-fly 20s ease-in-out infinite 2s" }}
       >
         🛸
       </div>
       <div
         className="absolute text-3xl sm:text-5xl drop-shadow-[0_0_15px_rgba(0,255,255,0.6)] opacity-0 will-change-transform"
         style={{
           animation: "ship-fly-reverse 25s ease-in-out infinite 8s",
           top: "25vh",
         }}
       >
         🛸
       </div>
       {!isMobile && (
         <>
           <div
             className="absolute text-5xl drop-shadow-[0_0_18px_rgba(0,255,255,0.7)] opacity-0 will-change-transform"
             style={{
               animation: "ship-fly 30s ease-in-out infinite 15s",
               top: "70vh",
             }}
           >
             🛸
           </div>
           <div
             className="absolute text-3xl drop-shadow-[0_0_12px_rgba(0,255,255,0.5)] opacity-0 will-change-transform"
             style={{
               animation: "ship-fly-reverse 22s ease-in-out infinite 3s",
               top: "45vh",
             }}
           >
             🛸
           </div>
         </>
       )}

       {/* Multiple satellites with different orbits */}
       <div
         className="absolute text-5xl sm:text-5xl drop-shadow-[0_0_15px_rgba(200,200,255,0.8)] opacity-0 will-change-transform"
         style={{
           animation: "satellite-orbit 35s linear infinite 5s",
           top: "15vh",
         }}
       >
         🛰️
       </div>
       {!isMobile && (
         <>
           <div
             className="absolute text-4xl drop-shadow-[0_0_12px_rgba(200,200,255,0.6)] opacity-0 will-change-transform"
             style={{
               animation: "satellite-orbit-reverse 40s linear infinite 12s",
               top: "60vh",
             }}
           >
             🛰️
           </div>
           <div
             className="absolute text-6xl drop-shadow-[0_0_20px_rgba(200,200,255,0.9)] opacity-0 will-change-transform"
             style={{
               animation: "satellite-orbit 28s linear infinite 20s",
               top: "30vh",
             }}
           >
             🛰️
           </div>
         </>
       )}
     </div>
   );
};

export default function Home() {
  const { persona, isLoading: isPersonaLoading } = usePersona();
  const personaName = !isPersonaLoading && persona.name ? persona.name : "Captain Sarthak";
  const { messages, isLoading, sendMessage } = useChat(personaName);

  return (
    <>
      <SpaceBackground />
      
      {/* Global scanlines effect */}
      <div className="scanlines" />

      <div className="relative z-10 flex flex-col h-screen max-w-5xl mx-auto p-4 sm:p-6">
        <div className="tech-frame flex-1 flex flex-col min-h-0 relative group">
          {/* Enhanced corner decorations */}
          <div className="tech-corner-tl group-hover:shadow-[0_0_15px_rgba(0,255,65,0.4)]" />
          <div className="tech-corner-tr group-hover:shadow-[0_0_15px_rgba(0,255,65,0.4)]" />
          <div className="tech-corner-bl group-hover:shadow-[0_0_15px_rgba(0,255,65,0.4)]" />
          <div className="tech-corner-br group-hover:shadow-[0_0_15px_rgba(0,255,65,0.4)]" />
          
          <div className="absolute -top-4 left-8 px-3 py-1 bg-black text-[9px] text-neon-green/70 font-mono tracking-[0.3em] z-30 uppercase border border-neon-green/30 rounded backdrop-blur">
            ◆ SYSTEM CONSOLE v4.0.2 ◆
          </div>
          <div className="absolute -bottom-4 right-8 px-3 py-1 bg-black text-[9px] text-neon-cyan/70 font-mono tracking-[0.3em] z-30 uppercase border border-neon-cyan/30 rounded backdrop-blur">
            ◆ TERMINAL ID: S-PA-413 ◆
          </div>

          <div className="terminal-container terminal-float flex flex-col flex-1 h-full rounded-lg overflow-hidden relative shadow-2xl">
            <div className="crt-overlay"></div>
            <Header
              name="Sarthak Pandey"
              role="Captain"
              resumeConfigured={persona.resume_configured}
              voiceEnabled={persona.voice_enabled}
            />

            <main className="flex-1 overflow-hidden flex flex-col">
               {!isPersonaLoading && !persona.resume_configured && (
                 <div className="mx-2 sm:mx-4 mt-2 sm:mt-4 border-2 border-neon-pink/60 bg-neon-pink/10 px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm text-neon-pink font-semibold rounded backdrop-blur animate-pulse">
                   <span className="font-bold">⚠ ALERT:</span> Resume grounding is offline. Initialize database sequence before mission critical deployment.
                 </div>
               )}

              <ChatWindow messages={messages} isLoading={isLoading} />
              <ChatInput onSend={sendMessage} isLoading={isLoading} />
            </main>

             {messages.length === 1 && (
               <div className="px-2 sm:px-4 pb-3 sm:pb-4 bg-gradient-to-t from-black/90 to-transparent backdrop-blur">
                 <p className="text-xs sm:text-sm text-neon-cyan/70 mb-3 font-mono uppercase tracking-widest flex items-center gap-2 font-bold">
                   <span className="animate-pulse">●</span> 💡 Suggested Queries:
                 </p>
                 <div className="flex flex-wrap gap-2 sm:gap-3 font-mono">
                   {[
                     "What are Captain Sarthak's AI engineering skills?",
                     "Show me his latest GitHub projects",
                     "Explain his experience with RAG",
                     "Request transmission to schedule interview",
                   ].map((q) => (
                     <button
                       key={q}
                       type="button"
                       onClick={() => sendMessage(q)}
                       className="text-xs sm:text-sm px-3 sm:px-4 py-1.5 sm:py-2 bg-gradient-to-br from-neon-green/15 to-neon-green/5 border-2 border-neon-green/50 text-neon-green hover:from-neon-green/30 hover:to-neon-green/15 hover:border-neon-cyan hover:shadow-[0_0_15px_rgba(0,217,255,0.3)] transition-all duration-300 whitespace-nowrap rounded font-semibold hover:scale-105 active:scale-95"
                     >
                       ➤ {q}
                     </button>
                   ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
