import { TimeSlot } from '@/lib/types';

export function formatSlot(slot: TimeSlot): string {
  if (slot.formatted) return slot.formatted;

  const date = new Date(slot.start);
  return date.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function truncate(str: string, max = 120): string {
  return str.length <= max ? str : str.slice(0, max).trimEnd() + '…';
}

export function formatSourceLabel(source: string): string {
  const [prefix, ...rest] = source.split(':');
  const label = rest.join(':').replace(/-/g, ' ');
  const icons: Record<string, string> = {
    github: '🔗 GitHub',
    resume: '📄 Resume',
  };
  return `${icons[prefix] ?? '📋 ' + prefix} · ${label}`;
}

export function formatRelevance(score: number): string {
  return `${Math.round(score * 100)}%`;
}
