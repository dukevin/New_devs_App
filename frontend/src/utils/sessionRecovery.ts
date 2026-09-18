/**
 * Session Recovery Utility
 * 
 * Recovers sessions through the configured authentication client.
 */

import { supabase } from '../lib/supabase';
import { Session } from '@supabase/supabase-js';

export class SessionRecovery {
  private static instance: SessionRecovery;
  private recoveryPromise: Promise<Session | null> | null = null;
  private recoveryStartTime: number | null = null;
  
  private constructor() {}
  
  static getInstance(): SessionRecovery {
    if (!SessionRecovery.instance) {
      SessionRecovery.instance = new SessionRecovery();
    }
    return SessionRecovery.instance;
  }
  
  /**
   * Attempts to recover a session from localStorage
   * This should be called on app initialization before any auth checks
   */
  async recoverSession(): Promise<Session | null> {
    if (typeof window !== 'undefined' && (window as any).__isLoggingOut) {
      console.log('[SessionRecovery] Skipping recovery - logout in progress');
      return null;
    }

    // If recovery is already in progress, check for timeout
    if (this.recoveryPromise) {
      const now = Date.now();
      // If recovery has been running for more than 10 seconds, reset it
      if (this.recoveryStartTime && now - this.recoveryStartTime > 10000) {
        console.log('[SessionRecovery] Recovery timeout - resetting');
        this.recoveryPromise = null;
        this.recoveryStartTime = null;
      } else {
        console.log('[SessionRecovery] Recovery already in progress, returning existing promise');
        return this.recoveryPromise;
      }
    }
    
    // Start new recovery
    this.recoveryStartTime = Date.now();
    
    // Create a new recovery promise with timeout
    let timeout: ReturnType<typeof setTimeout>;
    this.recoveryPromise = Promise.race([
      this.performRecovery(),
      new Promise<null>((resolve) => {
        timeout = setTimeout(() => {
          console.log('[SessionRecovery] Recovery timeout after 10s');
          resolve(null);
        }, 10000);
      })
    ]);
    
    try {
      const result = await this.recoveryPromise;
      return result;
    } finally {
      clearTimeout(timeout!);
      // Clear the promise after completion
      this.recoveryPromise = null;
      this.recoveryStartTime = null;
    }
  }
  
  private async performRecovery(): Promise<Session | null> {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      return session;
    } catch (error) {
      console.error('[SessionRecovery] Recovery error:', error);
      return null;
    }
  }
  /**
   * Ensures a session is properly persisted to localStorage
   */
  async persistSession(session: Session): Promise<void> {
    try {
      console.log('[SessionRecovery] Persisting session to storage...');
      
      await supabase.auth.setSession(session);
      
      console.log('[SessionRecovery] Session persisted successfully');
    } catch (error) {
      console.error('[SessionRecovery] Failed to persist session:', error);
    }
  }
  
  /**
   * Clears any stored session data
   */
  clearStoredSession(): void {
    try {
      localStorage.removeItem('base360-auth-token');
      console.log('[SessionRecovery] Stored session cleared');
    } catch (error) {
      console.error('[SessionRecovery] Failed to clear stored session:', error);
    }
  }

  /**
   * Alias for recoverSession to maintain compatibility with AuthContext
   * Returns user object wrapped for compatibility with legacy code
   */
  async tryRecover(): Promise<{ user: any } | null> {
    if (typeof window !== 'undefined' && (window as any).__isLoggingOut) {
      console.log('[SessionRecovery] Skipping tryRecover - logout in progress');
      return null;
    }

    try {
      const session = await this.recoverSession();
      if (session && session.user) {
        return { user: session.user };
      }
      return null;
    } catch (error) {
      console.error('[SessionRecovery] tryRecover failed:', error);
      return null;
    }
  }
}

export const sessionRecovery = SessionRecovery.getInstance();
