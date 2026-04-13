'use client';

import { useEffect, useState } from 'react';

import { getPersona } from '@/lib/api';
import { PersonaResponse } from '@/lib/types';

const defaultPersona: PersonaResponse = {
  name: 'AI Candidate',
  role: 'AI Engineer',
  booking_link: '',
  github_username: '',
  resume_configured: false,
  voice_enabled: false,
};

export function usePersona() {
  const [persona, setPersona] = useState<PersonaResponse>(defaultPersona);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadPersona() {
      try {
        const response = await getPersona();
        if (isMounted) {
          setPersona(response);
        }
      } catch (error) {
        console.error('Failed to load persona metadata:', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadPersona();

    return () => {
      isMounted = false;
    };
  }, []);

  return { persona, isLoading };
}
