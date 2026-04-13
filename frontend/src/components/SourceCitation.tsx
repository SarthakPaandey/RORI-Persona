import React from 'react';

import { Source } from '@/lib/types';

interface SourceCitationProps {
  source: Source;
}

export default function SourceCitation({ source }: SourceCitationProps) {
  const getSourceIcon = (sourceName: string) => {
    if (sourceName.startsWith('github:')) return '[GH]';
    if (sourceName.startsWith('resume:')) return '[DB]';
    return '[MEM]';
  };

  const getSourceLabel = (sourceName: string) => {
    if (sourceName.startsWith('github:')) {
      return `REPO: ${sourceName.replace('github:', '')}`;
    }
    if (sourceName.startsWith('resume:')) {
      return `DATACORE: ${sourceName.replace('resume:', '')}`;
    }
    return sourceName;
  };

  return (
    <div className="text-xs bg-[#00ff41]/5 px-3 py-2 border border-[#00ff41]/30 font-mono">
      <div className="flex items-center gap-2 font-bold text-[#00ff41]">
        <span className="opacity-70">{getSourceIcon(source.source)}</span>
        <span className="uppercase tracking-wider">{getSourceLabel(source.source)}</span>
        {source.relevance_score > 0 && (
          <span className="text-[#00ff41]/50 ml-auto bg-[#00ff41]/10 px-1 py-0.5 border border-[#00ff41]/20">
            MATCH: {(source.relevance_score * 100).toFixed(0)}%
          </span>
        )}
      </div>
       <p className="text-[#00ff41]/70 mt-2 border-l border-[#00ff41]/30 pl-2 line-clamp-2 italic">&quot;{source.content}&quot;</p>
    </div>
  );
}
