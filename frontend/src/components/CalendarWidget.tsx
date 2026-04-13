'use client';

import React, { useEffect, useState } from 'react';

import { bookMeeting } from '@/lib/api';
import { TimeSlot } from '@/lib/types';

interface CalendarWidgetProps {
  slots?: TimeSlot[];
  bookingLink?: string;
  timezone?: string;
}

export default function CalendarWidget({
  slots = [],
  bookingLink,
  timezone,
}: CalendarWidgetProps) {
  const [selectedSlot, setSelectedSlot] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [isBooking, setIsBooking] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!selectedSlot && slots.length > 0) {
      setSelectedSlot(slots[0].start);
    }
  }, [slots, selectedSlot]);

  async function handleBooking() {
    if (!selectedSlot || !name.trim() || !email.trim()) {
      setError('REQUIREMENTS NOT MET. PROVIDE DESIGNATION AND COMMS ID (EMAIL).');
      return;
    }

    setIsBooking(true);
    setError('');
    setSuccess('');

    try {
      const result = await bookMeeting({
        name: name.trim(),
        email: email.trim(),
        start_time: selectedSlot,
        timezone,
        notes: 'Transmission from Rori Console',
      });
      setSuccess(result.message);
    } catch (bookingError) {
      console.error('Booking failed:', bookingError);
      setError('TRANSMISSION FAILED. INITIATING BACKUP PROTOCOL.');
    } finally {
      setIsBooking(false);
    }
  }

   return (
     <div className="mt-3 p-3 sm:p-4 bg-black/50 border border-[#00ff41] shadow-[0_0_10px_rgba(0,255,65,0.2)]">
       <h3 className="font-bold text-[#00ff41] mb-2 uppercase tracking-widest border-b border-[#00ff41]/30 pb-1 text-sm sm:text-base">
         [ MISSION CALENDAR CONTROLS ]
       </h3>
       <p className="text-xs sm:text-sm text-[#00ff41]/80 mb-3 sm:mb-4">
         {slots.length > 0
           ? 'SELECT RENDEZVOUS COORDINATES BELOW:'
           : 'NO LIVE COORDINATES DETECTED. EXTERNAL FALLBACK AVAILABLE.'}
       </p>

      {slots.length > 0 && (
        <div className="space-y-3 sm:space-y-4">
          <div>
            <label className="block text-xs font-bold text-[#00ff41] mb-1 uppercase tracking-wider text-[10px] sm:text-xs">
              TEMPORAL COORDINATE
            </label>
            <select
              value={selectedSlot}
              onChange={(event) => setSelectedSlot(event.target.value)}
              className="w-full border border-[#00ff41]/50 bg-black/60 px-3 py-2 text-xs sm:text-sm text-[#00ff41] focus:outline-none focus:border-[#00ff41] min-h-[44px]"
            >
              {slots.map((slot) => (
                <option key={slot.start} value={slot.start}>
                  {slot.formatted}
                </option>
              ))}
            </select>
            {timezone && (
              <p className="mt-1 text-xs text-[#00ff41]/60">ZONE: {timezone}</p>
            )}
          </div>

           <div className="grid gap-2 sm:gap-3 sm:grid-cols-2">
             <input
               value={name}
               onChange={(event) => setName(event.target.value)}
               placeholder="DESIGNATION / NAME"
               className="border border-[#00ff41]/50 bg-black/60 px-3 py-2 text-xs sm:text-sm text-[#00ff41] focus:outline-none focus:border-[#00ff41] placeholder-[#00ff41]/30 uppercase min-h-[44px]"
             />
             <input
               type="email"
               value={email}
               onChange={(event) => setEmail(event.target.value)}
               placeholder="COMMS ID / EMAIL"
               className="border border-[#00ff41]/50 bg-black/60 px-3 py-2 text-xs sm:text-sm text-[#00ff41] focus:outline-none focus:border-[#00ff41] placeholder-[#00ff41]/30 uppercase min-h-[44px]"
             />
           </div>
 
           <button
             type="button"
             onClick={handleBooking}
             disabled={isBooking}
             className="w-full justify-center gap-2 px-4 py-2.5 sm:py-3 bg-[#00ff41]/20 text-[#00ff41] border border-[#00ff41] hover:bg-[#00ff41]/40 disabled:opacity-50 transition-colors text-xs sm:text-sm font-bold uppercase tracking-widest mt-2 min-h-[44px]"
           >
            {isBooking ? 'LOCKING COORDINATES...' : 'CONFIRM RENDEZVOUS'}
          </button>
        </div>
      )}

       {error && <p className="mt-3 text-xs sm:text-sm text-red-500 font-bold uppercase animate-pulse">{error}</p>}
       {success && <p className="mt-3 text-xs sm:text-sm text-[#00ff41] font-bold uppercase shadow-[0_0_5px_#00ff41] p-2 bg-[#00ff41]/10">{success}</p>}
 
       {bookingLink && (
         <a
           href={bookingLink}
           target="_blank"
           rel="noopener noreferrer"
           className="mt-3 sm:mt-4 block text-center gap-2 px-4 py-2 bg-black/50 text-[#00ff41] border border-[#00ff41]/50 hover:bg-[#00ff41]/20 transition-colors text-xs font-bold uppercase tracking-widest"
         >
           INITIATE MANUAL CAL.COM OVERRIDE &gt;&gt;
         </a>
       )}
    </div>
  );
}
