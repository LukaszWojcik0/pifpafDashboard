import type { Event } from './types';

export function todayIsoDate(now?: Date): string;
export function normalizeEventDate(value: unknown): string | null;
export function isPastEvent(event: Partial<Event>, now?: Date): boolean;
export function isUncertainEvent(event: Partial<Event>): boolean;
export function classifyEvent(event: Partial<Event>, now?: Date): 'public' | 'needs_review' | 'past';
export function eventVisibilityLabel(classification: 'public' | 'needs_review' | 'past'): string;
export function eventVisibilityReason(event: Partial<Event>, now?: Date): string;
