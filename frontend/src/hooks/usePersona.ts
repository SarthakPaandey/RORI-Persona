'use client';

import { useEffect, useState } from 'react';

import { getPersona } from '@/lib/api';
import { PersonaResponse } from '@/lib/types';

const defaultPersona: PersonaResponse = {
  name: '',
  role: '',
  booking_link: '',
  github_username: '',
  resume_configured: false,
  voice_enabled: false,
};

const PERSONA_RETRY_DELAYS_MS = [0, 1000, 2500, 5000];

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function usePersona() {
  const [persona, setPersona] = useState<PersonaResponse>(defaultPersona);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadPersona() {
      let loaded = false;

      for (let attempt = 0; attempt < PERSONA_RETRY_DELAYS_MS.length; attempt += 1) {
        if (!isMounted) return;

        const delayMs = PERSONA_RETRY_DELAYS_MS[attempt];
        if (delayMs > 0) {
          await sleep(delayMs);
          if (!isMounted) return;
        }

        try {
          const response = await getPersona();
          if (isMounted) {
            setPersona(response);
          }
          loaded = true;
          break;
        } catch (error) {
          console.error(
            `Failed to load persona metadata (attempt ${attempt + 1}/${PERSONA_RETRY_DELAYS_MS.length}):`,
            error
          );
        }
      }

      if (isMounted) {
        setIsLoading(false);
      }

      if (!loaded) {
        console.error('Persona metadata remained unavailable after retries.');
      }
    }

    loadPersona();

    return () => {
      isMounted = false;
    };
  }, []);

  return { persona, isLoading };
}
