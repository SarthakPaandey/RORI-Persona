'use client';

import { useCallback, useState } from 'react';

import { bookMeeting, getAvailability } from '@/lib/api';
import { TimeSlot } from '@/lib/types';

interface BookingData {
  name: string;
  email: string;
  start_time: string;
  notes?: string;
}

export function useCalendar() {
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [bookingLink, setBookingLink] = useState<string>('');
  const [isLoadingSlots, setIsLoadingSlots] = useState(false);
  const [isBooking, setIsBooking] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState<string | null>(null);

  const fetchSlots = useCallback(async () => {
    setIsLoadingSlots(true);
    try {
      const data = await getAvailability();
      setSlots(data.slots);
      setBookingLink(data.booking_link);
    } catch (err) {
      console.error('Failed to fetch slots:', err);
    } finally {
      setIsLoadingSlots(false);
    }
  }, []);

  const book = useCallback(async (data: BookingData) => {
    setIsBooking(true);
    setBookingError(null);
    setBookingSuccess(null);
    try {
      const result = await bookMeeting(data);
      setBookingSuccess(result.message);
      return result;
    } catch (err) {
      setBookingError('Booking failed. Please try using the direct link.');
      throw err;
    } finally {
      setIsBooking(false);
    }
  }, []);

  return {
    slots,
    bookingLink,
    isLoadingSlots,
    isBooking,
    bookingError,
    bookingSuccess,
    fetchSlots,
    book,
  };
}
